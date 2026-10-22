# ai-hub-demo

A small URL shortener. It is the demo app for [ai-hub](https://github.com/cekinmezyucel/ai-hub):
the agent builds its features from PRD Issues, one step at a time.

Features come through PRDs.

## API

- `GET /health` → `200 {"status": "ok"}`
- `POST /links` with `{"url": "<absolute http(s) URL, 1–2,048 characters>"}` creates a short link.
  - `201 {"code": "<code>", "short_url": "<base URL>/<code>"}`
  - `422 {"detail": ...}` when `url` is missing, too long, not `http`/`https`, has no host,
    or has spaces or control characters. The URL is stored exactly as sent.
- `GET /{code}` follows a short link.
  - `302` with `Location: <stored URL, percent-encoded>`. ASCII letters, digits, `-._~` and
    `:/%#?=@[]!$&'()*+,;` are kept; all other characters are UTF-8 percent-encoded.
    Examples: `|` → `%7C`, `{` → `%7B`, `é` → `%C3%A9`. `%` is kept, so an encoded URL is not
    encoded twice.
  - `404 {"detail": "Short link not found"}` for an unknown code.

Short links live in memory: they are lost when the app restarts.

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint
.venv/bin/pytest                                            # test
.venv/bin/uvicorn app.main:app --reload                     # run on :8000
```

CI (`.github/workflows/ci.yml`) runs lint, tests and a Docker build on every PR.

## Production (v0)

There is no hosted deploy. On every push to `main`, the `smoke` job in `ci.yml` builds the image,
starts it inside the job, runs the smoke checks against it and stops it.

Smoke checks live in `smoke/` and call the running app over HTTP (`BASE_URL`, default `http://localhost:8080`):

```sh
BASE_URL=http://localhost:8080 .venv/bin/pytest smoke -v   # smoke checks against a running app
```

One file per feature: `smoke/test_<issue>_<slug>.py` (feature key with `_`), one test per acceptance
criterion: `test_ac_<n>_<what>`. Smoke checks are read-only unless the spec names safe test data.
