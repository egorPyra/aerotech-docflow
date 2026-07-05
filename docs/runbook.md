# Runbook

Operational notes for local development and future production support.

## Local Startup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Scan Endpoint Smoke Test

```bash
curl -X POST http://127.0.0.1:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"planfix_task_id":52418,"doc_type":"NKL","number":"001","date":"2026-06-24"}'
```

Expected response:

```json
{
  "status": "accepted",
  "message": "Scan workflow accepted. Scanner implementation is not configured yet."
}
```

## Configuration

Runtime configuration comes from environment variables or `.env`.

Important settings:

- `APP_ENV`
- `DEBUG`
- `SCANNER_INBOX_DIR`
- `ARCHIVE_DIR`
- `PLANFIX_BASE_URL`
- `PLANFIX_API_TOKEN`
- `PLANFIX_TIMEOUT_SECONDS`

## Troubleshooting

- If the app does not start, confirm dependencies are installed from `requirements.txt`.
- If settings are not applied, confirm `.env` exists in the process working directory.
- If storage fails later, confirm the process can create and write to archive directories.
- Real scanner and Planfix behavior is not available in the current skeleton.
