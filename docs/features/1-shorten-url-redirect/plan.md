# Plan: Shorten a URL and redirect to it

Feature: 1-shorten-url-redirect · Spec: ./spec.md · Risk: medium — two new public endpoints, and one of them redirects to a URL the client sent · Verdict: pass

## Commands
| Purpose | Command | Found in |
|---------|---------|----------|
| install | `pip install -r requirements-dev.txt` | `.github/workflows/ci.yml:21` |
| test    | `pytest` | `.github/workflows/ci.yml:25` |
| lint    | `ruff check . && ruff format --check .` | `.github/workflows/ci.yml:23` |
| run     | `uvicorn app.main:app --reload` | `README.md:14` |
| smoke   | `BASE_URL=http://localhost:8080 pytest smoke -v` | `.github/workflows/ci.yml:56`, `README.md:27` |

## Approach
- All code stays in `app/main.py`, next to `/health` (P-2, P-4). Links live in a module-level `dict[str, str]` (code → URL): the spec puts restarts out of scope.
- Request model `LinkIn(BaseModel)` with `url: str = Field(min_length=1, max_length=2048)` and a `field_validator` that uses `urllib.parse.urlsplit`: scheme (lower-cased only for the check) is `http` or `https`, `hostname` is set, and the URL has no whitespace or control characters (covers A-4 leading/trailing spaces; P-5). A `ValueError` in the validator gives FastAPI's normal `422`.
- **Rejected:** pydantic `AnyHttpUrl`. It normalises the URL (adds `/`, lower-cases the host), so `Location` would not be "exactly" what was sent (AC-2, A-4). (`Location` is percent-encoded; see feature 3-redirect-location-exact-url.)
- Code: 7 characters from `string.ascii_letters + string.digits` with `secrets.choice` (A-2); pick again while the code is taken. Reserved paths (`health`, `links`, `docs`, `redoc`, `openapi.json`) can never match, because none is 7 alphanumeric characters.
- Redirect with Starlette `RedirectResponse(url, status_code=302)` (A-1). `short_url` = `str(request.base_url).rstrip("/") + "/" + code` (A-3).
- `GET /{code}` is declared after `/health` and `/links`; FastAPI adds `/docs`, `/redoc`, `/openapi.json` at app creation, so they still match first.

## Tasks
### T-1 Create a short link (`POST /links`)
- Covers: AC-1, AC-3, AC-4; part of AC-5 (two codes differ). P-11 (log on create), P-12 (README).
- Files:
  - `app/main.py` (change) — pattern from `app/main.py` (`/health` route). Add `LinkIn`, the store, the code generator, `POST /links` → `201`. Add `logger = logging.getLogger(__name__)` and `logging.basicConfig(level=logging.INFO)` so `INFO` lines reach `docker logs`. Log `"short link created code=%s"`, never the URL.
  - `tests/test_links.py` (new) — pattern from `tests/test_health.py`.
  - `smoke/test_1_shorten_url_redirect.py` (new) — pattern from `smoke/test_health.py`, naming rule from `README.md:30-31`.
  - `README.md` (change) — replace "Today it only has `GET /health`" and document `POST /links` (request, `201`, `422`).
- Test first: `tests/test_links.py`:
  - `test_create_link_returns_code_and_short_url` — `201`; body has exactly `code` and `short_url`; `code` matches `^[A-Za-z0-9]{7}$`; `short_url == "http://testserver/" + code`.
  - `test_create_link_rejects_invalid_url` (parametrized: `javascript:alert(1)`, `ftp://example.com`, `/relative/path`, `https://`, `""`, `" https://example.com"`, `"https://example.com "`, `123`) — `422`, JSON body has `detail`, no `code` / `short_url`.
  - `test_create_link_rejects_missing_url` — body `{}` → `422`, same checks.
  - `test_create_link_rejects_non_json_body` — `content=b"not json"` → `422`.
  - `test_create_link_accepts_2048_chars` / `test_create_link_rejects_2049_chars` — build `"https://example.com/" + "a" * n` to the exact length; `201` / `422`.
  - `test_create_link_accepts_upper_case_scheme` — `HTTPS://example.com` → `201`.
  - `test_create_link_twice_gives_different_codes` — same URL twice → two `201`, codes differ.
  - `test_create_link_logs_code_not_url` (`caplog`) — log text holds the code, not the URL (`https://example.com/?token=secret-value`).
- Smoke first: `smoke/test_1_shorten_url_redirect.py::test_ac_1_create_link`, `::test_ac_3_invalid_url_rejected`, `::test_ac_4_url_length_limit`. Safe live: the v0 production app runs inside the CI job, keeps links in memory only and is removed after the job; test data uses the reserved domain `example.com`.
- Done when: the new tests pass; `pytest` and lint are green; `GET /health` test still passes.

### T-2 Follow a short link (`GET /{code}`)
- Covers: AC-2, AC-5, AC-6. P-11 (log on 404), P-12 (README).
- Files:
  - `app/main.py` (change) — pattern from `app/main.py`. `GET /{code}`: found → `RedirectResponse(url, status_code=302)`; not found → log `"short link not found code=%s"` (warning) and `raise HTTPException(status_code=404, detail="Short link not found")`.
  - `tests/test_links.py` (change).
  - `smoke/test_1_shorten_url_redirect.py` (change).
  - `README.md` (change) — document `GET /{code}` (`302`, `404`) and that links are lost on restart.
- Test first: `tests/test_links.py` (all `GET` calls use `follow_redirects=False`; Starlette `TestClient` follows redirects by default):
  - `test_follow_link_redirects_to_url` — create `https://example.com/some/long/path?x=1`; `GET /<code>` → `302`, `Location` is exactly that URL (`Location` is percent-encoded; see feature 3-redirect-location-exact-url).
  - `test_follow_link_keeps_query_and_fragment` — `https://example.com/p?a=1&b=2#frag` comes back unchanged.
  - `test_follow_link_keeps_upper_case_scheme` — `Location` is `HTTPS://example.com` as sent (`Location` is percent-encoded; see feature 3-redirect-location-exact-url).
  - `test_same_url_twice_both_codes_redirect` — both codes → `302` to the same URL.
  - `test_unknown_code_returns_404` — `GET /doesnotexist` → `404`, body `{"detail": "Short link not found"}`, no `location` header.
  - `test_unknown_code_logs_code` (`caplog`) — log text holds `doesnotexist`.
  - `test_docs_still_served` — `GET /docs` → `200` (route order). `GET /health` stays covered by `tests/test_health.py`.
- Smoke first: `smoke/test_1_shorten_url_redirect.py::test_ac_2_redirect_to_url`, `::test_ac_5_same_url_twice`, `::test_ac_6_unknown_code_404`. httpx does not follow redirects by default, so the smoke `client` fixture needs no change.
- Done when: the new tests pass; `pytest` and lint are green.

### T-3 Log rejected requests without the URL
- Covers: P-11 (spec "Non-functional": every error is logged; the long URL is not logged). Supports AC-3, AC-4.
- Files:
  - `app/main.py` (change) — pattern from FastAPI's documented override: `@app.exception_handler(RequestValidationError)` that logs `"invalid request path=%s errors=%s"` with only each error's `loc` and `type` (warning), then returns `await request_validation_exception_handler(request, exc)` from `fastapi.exception_handlers`, so the `422` body stays the same.
  - `tests/test_links.py` (change).
- Test first: `tests/test_links.py::test_invalid_request_logged_without_url` (`caplog`) — `POST /links` with `" https://example.com/?token=secret-value"` → `422`; one warning record mentions `/links`; `secret-value` is not in `caplog.text`. Plus `test_invalid_request_body_unchanged` — `422` body still has `detail` as a list with `loc` `["body", "url"]`.
- Done when: the new tests pass; T-1 `422` tests still pass unchanged; `pytest` and lint are green.

## Traceability
| AC   | Tasks | Tests |
|------|-------|-------|
| AC-1 | T-1 | `tests/test_links.py::test_create_link_returns_code_and_short_url`, `smoke/test_1_shorten_url_redirect.py::test_ac_1_create_link` |
| AC-2 | T-2 | `tests/test_links.py::test_follow_link_redirects_to_url`, `smoke/test_1_shorten_url_redirect.py::test_ac_2_redirect_to_url` |
| AC-3 | T-1, T-3 | `tests/test_links.py::test_create_link_rejects_invalid_url`, `::test_create_link_rejects_missing_url`, `smoke/test_1_shorten_url_redirect.py::test_ac_3_invalid_url_rejected` |
| AC-4 | T-1, T-3 | `tests/test_links.py::test_create_link_accepts_2048_chars`, `::test_create_link_rejects_2049_chars`, `smoke/test_1_shorten_url_redirect.py::test_ac_4_url_length_limit` |
| AC-5 | T-1, T-2 | `tests/test_links.py::test_create_link_twice_gives_different_codes`, `::test_same_url_twice_both_codes_redirect`, `smoke/test_1_shorten_url_redirect.py::test_ac_5_same_url_twice` |
| AC-6 | T-2 | `tests/test_links.py::test_unknown_code_returns_404`, `smoke/test_1_shorten_url_redirect.py::test_ac_6_unknown_code_404` |

## Risks and rollback
- **Open redirect / bad schemes (P-5).** The validator is the only guard. T-1 tests every bad input from AC-3 plus whitespace. Any redirect to an `http(s)` host is still possible by design (spec scope).
- **`Location` encoding.** Starlette percent-encodes characters outside `:/%#?=@[]!$&'()*+,;` and letters/digits (`starlette/responses.py:218`), for example `|`, `{`, `^` or non-ASCII. Such a URL is accepted but its `Location` is the encoded form. All AC and edge-case URLs are not changed. If this matters, it is a spec change, not a fix here.
- **Memory.** No limit on stored links (A-5). A large number of `POST /links` calls grows memory until restart. Accepted by the spec.
- **Catch-all route.** `GET /{code}` answers every one-segment path that no other route matches (for example `/favicon.ico` → `404` "Short link not found"). Tested: `/health` and `/docs` still work.
- **Rollback.** No data, no migration, no config. Revert the feature commits; the store is in memory, so nothing is left behind.
