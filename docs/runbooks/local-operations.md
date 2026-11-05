# Local operations runbook

This runbook describes checks available in the local TestFlow environment. It is not production deployment evidence.

## Readiness and correlation

`GET /healthz` queries PostgreSQL and pings Redis. It returns HTTP 200 with `status: ok` when both are available, otherwise HTTP 503 with `status: unavailable`. The response reports only `database` and `redis` booleans. It does not verify a Celery worker, storage capacity, or external OCR providers.

Every HTTP response includes `X-Request-ID`. A caller may supply an ID of 8–64 ASCII letters, digits, underscores, or hyphens. The server generates a new ID for any other value. JSON stdout request logs include this ID, method, path, status, and duration. Import logs also include job ID, stage, and latency. Request bodies and query strings are not logged by this middleware. Retention, alert routing, and a production log sink are not yet configured.

## Admin view

An Admin can open the **Vận hành** page or call `GET /api/v1/ops/summary/` with a valid access token. It reports import job state counts, oldest review age, pending publication requests, and `BUILD_SHA`. Non Admin accounts cannot use this endpoint. The summary contains no exam or question text. Set `BUILD_SHA` to the deployed revision for useful incident correlation.

## TXT import quota

`IMPORT_DAILY_JOB_LIMIT` defaults to 20 successfully created import jobs per uploader per local calendar day (`Asia/Ho_Chi_Minh`). It includes later discarded jobs. The upload endpoint returns HTTP 429 with code `UPLOAD_QUOTA_EXCEEDED` after the limit. Duplicate-file detection takes precedence and returns HTTP 409. Concurrent requests from the same uploader are serialized by a database row lock. This limit applies to TXT upload; document OCR import is not available yet.

## Local checks

With the development stack running, open `http://127.0.0.1:8000/healthz`. Check Admin **Vận hành** after a TXT upload and confirm the job state count changes. Match an API response's `X-Request-ID` with its JSON stdout line. The backend suite includes health, permission, state transition, quota, and correlation checks; the browser suite includes an Admin summary journey.

## Current release gaps

Production host, domain, TLS termination, backup destination and restore exercise, alerting, on-call ownership, deployment credentials, and authorized real data are not configured or verified. Do not treat the local probe or Admin dashboard as proof of production readiness.
