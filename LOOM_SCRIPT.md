# Loom Demo — Talking Points

Keep it to 3-5 minutes. Structure:

## 1. Live demo (60-90 sec)
- Open the deployed URL
- Audit a normal site (e.g. a company homepage) — show the report render
- Audit something that should fail gracefully — e.g. type "not a url" or
  a URL that 404s — show the clean error message, not a crash
- (Optional) audit a non-HTML URL, e.g. a raw JSON/API endpoint, to show
  the content-type check working

## 2. Code walkthrough (90-120 sec)
- Open `app/audit.py`, briefly show `validate_url` -> `fetch_page` ->
  `build_report` as a pipeline
- Point out this file has zero Flask imports — that's why the tests in
  `tests/test_audit.py` don't need to spin up a server
- Open `tests/test_audit.py`, run `pytest` on screen, show them passing

## 3. Self-critique — the part that matters most here (60-90 sec)
Pick ONE of these (pick whichever is actually true for you — genuine
self-critique reads better than a rehearsed one):

- **Concurrency**: right now the app handles one audit request at a
  time synchronously. With another day I'd add a job queue (or at least
  `async`/background threading) so slow target sites don't block other
  users' requests.
- **Caching**: every audit re-fetches the URL from scratch. I'd add a
  short-lived cache (e.g. Redis, or even an in-memory TTL dict) keyed on
  URL so repeated audits of the same page within a few minutes don't
  hit the target site again.
- **Deeper SEO checks**: right now it's intentionally minimal (status,
  title, meta, H1, alt text, word count) to match the spec exactly.
  With more time I'd add: multiple H1 detection warnings, canonical tag
  presence, broken internal link checking, and image size/lazy-loading
  hints.
- **No persistence**: results aren't stored anywhere, so there's no
  history of past audits per URL. I'd add a small SQLite table to track
  audits over time and show trend deltas.

Say it plainly: "If I had another day, I'd add X, because Y." Don't
just list a feature — explain the reasoning, since that's literally
what's being scored (not just "self-critique" but "reasoning behind
each" decision).

## Recording tips
- Screen + voice, not just voice over a static screen
- Don't script word-for-word — bullet points above are enough
- Keep energy up; a flat monotone reads as disengaged even if the
  content is good
