# pdf-service — Technical Documentation

## Overview

`pdf-service` manages PDF document access based on subscription plans. It receives user identity and plan information via headers from the API gateway, enforces daily reading limits using Redis, serves PDF files via pre-signed URLs from S3 or Azure Blob, and persists reading history to MySQL.

---

## Architecture

```
api-gateway
     │
     │  X-User-ID: uuid
     │  X-User-Plan: free|basic|premium
     ▼
pdf-service (FastAPI :8000)
     │
     ├──► Redis (session counters, daily limits)
     ├──► MySQL (reading history, PDF catalog)
     └──► S3 / Azure Blob (PDF file storage)
```

---

## API Reference

### GET /pdfs

List all available PDFs.

**Headers:** `X-User-ID`, `X-User-Plan`

**Response 200:**
```json
[
  {
    "id": 1,
    "title": "Introduction to Python",
    "filename": "intro-python.pdf",
    "description": "A beginner's guide to Python programming",
    "created_at": "2026-01-01T00:00:00"
  }
]
```

---

### GET /pdfs/{id}

Get metadata for a specific PDF.

**Response 200:**
```json
{
  "id": 1,
  "title": "Introduction to Python",
  "filename": "intro-python.pdf",
  "description": "A beginner's guide",
  "created_at": "2026-01-01T00:00:00"
}
```

**Response 404:**
```json
{"detail": "PDF not found"}
```

---

### POST /pdfs/{id}/open

Open a reading session. Checks plan limits, starts a session in Redis, returns a pre-signed download URL.

**Headers:** `X-User-ID`, `X-User-Plan`

**Response 200:**
```json
{
  "success": true,
  "message": "Reading session started",
  "url": "https://s3.amazonaws.com/bucket/file.pdf?X-Amz-Signature=...",
  "session_id": "abc123-uuid"
}
```

**Response 403 — limit reached:**
```json
{"detail": "Daily PDF limit reached"}
```

**Response 403 — time exceeded (free plan):**
```json
{"detail": "Daily reading time exceeded (30 minutes)"}
```

**Response 403 — already reading:**
```json
{"detail": "You already have an active reading session. Close it first."}
```

---

### POST /pdfs/{id}/close

Close the active reading session. Calculates duration, persists to MySQL, updates daily time in Redis.

**Headers:** `X-User-ID`, `X-User-Plan`

**Response 200:**
```json
{
  "success": true,
  "message": "Reading session ended",
  "duration_seconds": 542
}
```

**Response 400 — no active session:**
```json
{"detail": "No active reading session found"}
```

---

### GET /health

Kubernetes liveness/readiness probe.

**Response 200:**
```json
{"status": "ok"}
```

---

## Access Control Rules

| Plan | Max PDFs/day | Max time/day | Enforcement |
|---|---|---|---|
| Free | 1 | 1800 seconds (30 min) | Redis counter + timer |
| Basic | 1 | Unlimited | Redis counter only |
| Premium | Unlimited | Unlimited | No checks |
| Unknown/missing | 0 | 0 | Always denied |

---

## Redis Key Patterns

| Key | Value | TTL | Purpose |
|---|---|---|---|
| `pdf:session:{user_id}` | JSON (session_id, pdf_id, plan, started_at) | 1 hour | Active reading session |
| `pdf:daily_count:{user_id}:{date}` | integer | 24 hours | PDFs opened today |
| `pdf:daily_time:{user_id}:{date}` | seconds (integer) | 24 hours | Total reading time today |

Daily keys auto-reset via TTL — no scheduled cleanup needed.

---

## MySQL Tables

### pdfs

| Column | Type | Description |
|---|---|---|
| id | INT AUTO_INCREMENT | Primary key |
| title | VARCHAR(255) | PDF display title |
| filename | VARCHAR(255) | S3 key or Azure blob name |
| description | TEXT | Optional description |
| created_at | TIMESTAMP | When the PDF was added |

### reading_sessions

| Column | Type | Description |
|---|---|---|
| id | INT AUTO_INCREMENT | Primary key |
| user_id | VARCHAR(36) | User UUID from X-User-ID |
| pdf_id | INT (FK → pdfs.id) | Which PDF was read |
| started_at | TIMESTAMP | Session start time |
| ended_at | TIMESTAMP | Session end time (null if active) |
| duration_seconds | INT | Calculated on close |
| plan_type | VARCHAR(20) | Plan at time of reading |
| created_at | TIMESTAMP | Record creation time |

---

## Storage Abstraction

The `STORAGE_BACKEND` env var switches between S3 and Azure Blob:

### S3
- Uses `boto3` to generate pre-signed GET URLs
- URL valid for `PRESIGNED_URL_TTL` seconds (default 30 minutes)
- Client downloads directly from S3 — no traffic through the service

### Azure Blob
- Uses `azure-storage-blob` to generate SAS URLs
- Same TTL behavior
- Client downloads directly from Azure — no traffic through the service

---

## Session Lifecycle

```
1. POST /pdfs/{id}/open
   ├── Check Redis: active session exists? → 403
   ├── Check Redis: daily count >= limit? → 403
   ├── Check Redis: daily time >= 1800s (free only)? → 403
   ├── Generate pre-signed URL from S3/Azure
   ├── Store session in Redis (TTL 1h)
   ├── Increment daily count in Redis
   └── Return URL + session_id

2. User reads the PDF...

3. POST /pdfs/{id}/close
   ├── Read session from Redis
   ├── Calculate duration = now - started_at
   ├── Insert ReadingSession into MySQL
   ├── Add duration to daily_time in Redis
   ├── Delete session from Redis
   └── Return duration_seconds
```

If the user never calls `/close`, the Redis session key expires after 1 hour automatically. The reading time is NOT persisted in that case (best effort).

---

## Network Policy

- **Ingress:** only from pods with label `app: api-gateway` on port 8000
- **Egress:** only to `pdf-service-mysql` (3306), `pdf-service-redis` (6379), HTTPS (443 for S3/Azure), DNS (53)

No other service in the cluster can reach pdf-service directly.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing X-User-ID header | 401 "X-User-ID header required" |
| Missing X-User-Plan header | 403 "No active subscription" |
| PDF not found | 404 "PDF not found" |
| Daily PDF limit reached | 403 with reason |
| Daily time exceeded (free) | 403 with reason |
| Already has active session | 403 with reason |
| No active session on close | 400 "No active reading session found" |
| S3/Azure unreachable | 500 (unhandled — let it fail loudly) |
