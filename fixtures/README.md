# Fixtures

This directory contains sample payloads and responses for testing and development.

## Webhook Payloads

| File | Description | Expected Response |
|------|-------------|-------------------|
| `webhook_mention_roadmap_valid.json` | Valid `@pulse roadmap` with JSON block | 202 Accepted |
| `webhook_mention_roadmap_no_json.json` | `@pulse roadmap` without JSON block | 422 Unprocessable Entity |
| `webhook_mention_roadmap_invalid_schema.json` | `@pulse roadmap` with invalid JSON schema (missing `goal`) | 422 Unprocessable Entity |
| `webhook_reply.json` | Reply event (not a mention) | 204 No Content |
| `webhook_mention_no_command.json` | Mention without `@pulse` command | 204 No Content |
| `webhook_mention_unsupported_command.json` | `@pulse unknown` command | 204 No Content |
| `webhook_mention_guard_reject.json` | Mention with malicious input (prompt injection) | 400 Bad Request |

## Worker Responses

| File | Description |
|------|-------------|
| `worker_response_success.json` | Successful roadmap generation with 5 phases |
| `worker_response_failed.json` | Failed generation with error details |

## Misskey API Responses

| File | Description |
|------|-------------|
| `misskey_reply_success.json` | Successful reply post |
| `misskey_reply_failure.json` | Failed reply (auth error) |

## Usage

### Testing Webhooks

```bash
# Valid roadmap request
curl -X POST http://localhost:8000/webhooks/misskey \
  -H "Content-Type: application/json" \
  -H "X-Misskey-Hook-Secret: your-secret" \
  -d @fixtures/webhook_mention_roadmap_valid.json

# Invalid request (no JSON block)
curl -X POST http://localhost:8000/webhooks/misskey \
  -H "Content-Type: application/json" \
  -H "X-Misskey-Hook-Secret: your-secret" \
  -d @fixtures/webhook_mention_roadmap_no_json.json
```

### Testing Worker Adapter

```python
import json
from adapters.roadmap_design_skill import transform_roadmap_request, extract_reply_text

with open('fixtures/webhook_mention_roadmap_valid.json') as f:
    webhook = json.load(f)

# Transform simple request to worker format
worker_request = transform_roadmap_request(
    webhook['body']['note']['text'],
    trace_id='test_trace'
)

# Extract reply from worker response
with open('fixtures/worker_response_success.json') as f:
    response = json.load(f)

reply_text = extract_reply_text(response)
```