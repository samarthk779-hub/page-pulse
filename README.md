# Page Pulse

A small web tool that audits any URL and returns a JSON report covering
HTTP status, response time, title, meta description, H1 count, images
missing alt text, and an approximate word count.

## AI tool use

I used Claude (Anthropic) to scaffold this project — the Flask app
structure, the initial URL validation/parsing logic in app/audit.py,
the frontend, and the test suite. I reviewed the generated code
line by line, ran the full test suite myself, and caught two real
bugs during testing (a URL-scheme handling issue with ftp:// links,
and a word-count bug that was incorrectly counting <title> text as
page content). I made the call to separate the parsing logic from
the Flask routes so it could be unit tested independently. I also
handled the actual deployment myself, including diagnosing and
fixing a gunicorn start-command mismatch (app:app vs run:app) that
was causing the live deploy to fail on Render.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Visit `http://127.0.0.1:5000`.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Tests live in `tests/test_audit.py` and cover the parsing/validation
logic in isolation (no real network calls — `requests.get` is mocked):
- Happy path: a full HTML page parses into the correct report fields
- URL validation: empty input, malformed input, non-http(s) schemes
- Fetch failures: timeout, connection error, non-HTML content type,
  oversized response
- Edge cases: missing `<title>`/meta description, word count correctly
  excludes `<head>` and `<script>` content

## API

`POST /api/audit`

Request body:
```json
{ "url": "https://example.com" }
```

Success response (`200`):
```json
{
  "url": "https://example.com",
  "final_url": "https://example.com/",
  "http_status": 200,
  "response_time_ms": 123.4,
  "title": "Example Domain",
  "meta_description": null,
  "h1_count": 1,
  "image_count": 0,
  "images_missing_alt": 0,
  "word_count": 28
}
```

Error response (`4xx`/`5xx`):
```json
{ "error": "That doesn't look like a valid URL." }
```

## Design decisions

**1. Separated parsing logic from Flask routing (`app/audit.py` vs `app/routes.py`).**
`audit.py` has no Flask imports at all — `validate_url`, `fetch_page`, and
`build_report` are plain functions that take and return ordinary Python
values. This meant the entire test suite in `tests/test_audit.py` runs
without spinning up a server or mocking Flask's request context, and the
logic could be reused outside a web app (a CLI tool, a batch job) with
no changes. The trade-off is one extra layer of indirection versus
putting everything straight into the route handler — worth it here since
"correctness of parsing logic" is explicitly a graded criterion.

**2. Streamed the fetch with a hard size cap instead of just checking
`Content-Length` after the fact.** A malicious or misconfigured server
could omit `Content-Length` or lie about it, so I read the response in
chunks via `iter_content()` and abort as soon as the running total
exceeds 5 MB, rather than trusting a header. This trades a little extra
code for actually enforcing the limit rather than just checking for it.

**3. Raised a single custom `AuditError(message, status_code)` exception
for every expected failure mode, instead of returning `(None, error)`
tuples or letting library exceptions (`requests.exceptions.Timeout`,
etc.) propagate to the route.** The route handler ends up with one
`except AuditError` clause and one catch-all `except Exception` as a
last line of defense — so no fetch/parse failure can produce a raw 500
with a stack trace leaking to the client, and adding a new failure case
later only means raising `AuditError` somewhere, not touching the route.

## Deploying (Render, free tier)

1. Push this repo to GitHub.
2. On [Render](https://render.com), click **New > Blueprint** and point it
   at the repo — `render.yaml` configures the build/start commands
   automatically. (Or create a **Web Service** manually with build command
   `pip install -r requirements.txt` and start command `gunicorn run:app`.)
3. Once deployed, grab the live URL for submission.

## Project structure

```
page-pulse/
├── app/
│   ├── __init__.py     # Flask app factory
│   ├── audit.py        # URL validation, fetch, HTML parsing (framework-agnostic)
│   ├── routes.py       # Thin Flask routes over app/audit.py
│   └── templates/
│       └── index.html  # Frontend
├── tests/
│   └── test_audit.py    # Unit tests for app/audit.py
├── run.py               # Entry point
├── requirements.txt
├── requirements-dev.txt # + pytest, for running the test suite
├── Procfile
└── render.yaml
```
