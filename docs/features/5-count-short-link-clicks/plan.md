# Plan: Count clicks on a short link

Feature: 5-count-short-link-clicks · Spec: ./spec.md · Risk: medium — new public endpoint `GET /links/{code}/clicks` (new contract); no auth, data migration or breaking change · Verdict: pass

## Commands
| Purpose | Command | Found in |
|---------|---------|----------|
| install | `pip install -r requirements-dev.txt` | `.github/workflows/ci.yml:21` |
| test    | `pytest` | `.github/workflows/ci.yml:25` |
| lint    | `ruff check . && ruff format --check .` | `.github/workflows/ci.yml:23` |
| run     | `uvicorn app.main:app --reload` | `README.md:30` |
| smoke   | `BASE_URL=http://localhost:8080 pytest smoke -v` | `.github/workflows/ci.yml:56`, `README.md:43` |

## Approach
- Keep counts in a second in-memory dict `clicks: dict[str, int]` next to `links` in `app/main.py`. `POST /links` sets `clicks[code] = 0`; `GET /{code}` adds one only on the `302` path, after the lookup succeeds.
- Guard the `+= 1` with a `threading.Lock`. Sync FastAPI endpoints run in a thread pool, and `dict[k] += 1` is not atomic (spec edge case "no click is lost").
- `HEAD /{code}` needs no code: FastAPI `APIRoute` registers only the methods given (`.venv/.../fastapi/routing.py:1072-1074`), so `HEAD /{code}` never reaches `follow_link` today (expected `405`). T-2 pins that the count stays `0`; the `HEAD` response itself is not changed or asserted beyond "not `302`".
- The new route `/links/{code}/clicks` has three path segments; `/{code}` matches one segment only, so the routes cannot clash (spec A-1).
- **Rejected:** change `links` to `dict[str, Link]` with a `url` and a `clicks` field. It touches `new_code`, `create_link` and `follow_link` for no gain; a second dict is the smallest change (P-2).

## Tasks
### T-1 Count each `302` and read the count
- Covers: AC-1, AC-2, AC-3, AC-5, AC-6. P-8, P-11 (warning on unknown read).
- Files:
  - `app/main.py` (change) — add `clicks` dict and `clicks_lock`; set `0` in `create_link`; add one in `follow_link` under the lock; new `ClicksOut(code: str, clicks: int)` model, pattern from `LinkOut` (`app/main.py:42`); new `@app.get("/links/{code}/clicks")` endpoint `read_clicks`, pattern from `follow_link` (`app/main.py:75-82`): unknown code → `logger.warning("short link clicks not found code=%r", code)` and `HTTPException(404, "Short link not found")`.
  - `tests/test_links.py` (change) — pattern from `test_follow_link_redirects_to_url` (uses `_create`, `follow_redirects=False`).
  - `smoke/test_5_count_short_link_clicks.py` (new) — pattern from `smoke/test_3_redirect_location_exact_url.py`, naming rule from `README.md:46-47`.
- Test first: `tests/test_links.py`:
  - `test_new_link_has_zero_clicks` — `_create`; `GET /links/<code>/clicks` → `200`, body `== {"code": code, "clicks": 0}` (AC-1).
  - `test_each_follow_adds_one_click` — `GET /<code>` 3 times, each `302`; count `== 3` (AC-2).
  - `test_clicks_counted_per_link` — links A and B; follow A 2 times; A `== 2`, B `== 0` (AC-3).
  - `test_clicks_of_unknown_code_returns_404` — `GET /links/doesnotexist/clicks` → `404`, body `== {"detail": "Short link not found"}` (AC-5).
  - `test_clicks_of_unknown_code_logs_warning` — one `WARNING` record from `app.main` that contains `doesnotexist` (P-11).
  - `test_reading_clicks_does_not_add_clicks` — follow 2 times; read 3 times; every body has `"clicks": 2` (AC-6).
- Smoke first: `smoke/test_5_count_short_link_clicks.py::test_ac_1_new_link_zero_clicks`, `::test_ac_2_three_follows_three_clicks`, `::test_ac_3_counts_per_link`, `::test_ac_5_unknown_code_404`, `::test_ac_6_read_does_not_count`. Safe live (spec A-4): links to `https://example.com/` in memory only; the v0 app runs inside the CI job and is removed after it. httpx does not follow redirects by default.
- Done when: the new tests pass; all existing tests pass unchanged; `pytest` and lint are green.

### T-2 Pin what must not count or leak
- Covers: AC-4, AC-7, AC-8, AC-10. Spec edge cases "many clients at the same time" and "code with a newline".
- Files:
  - `tests/test_links.py` (change) — same pattern as T-1; log checks follow `test_create_link_logs_code_not_url` and `test_unknown_code_log_cannot_forge_lines`.
  - `smoke/test_5_count_short_link_clicks.py` (change).
- Test first: `tests/test_links.py`:
  - `test_unknown_code_follow_does_not_change_count` — follow a link once; `GET /doesnotexist` → `404`; count still `1` (AC-4).
  - `test_clicks_store_and_log_no_visitor_data` — follow with headers `User-Agent: ac7-agent`, `X-Forwarded-For: 203.0.113.7`; read count; `set(body) == {"code", "clicks"}`; `caplog.text` contains neither `ac7-agent` nor `203.0.113.7` (AC-7).
  - `test_head_does_not_count` — `client.head(f"/{code}", follow_redirects=False)` status is not `302`; count stays `0` (AC-8).
  - `test_post_and_follow_responses_keep_their_shape` — after reading the count, `POST /links` body keys `== {"code", "short_url"}` and `GET /<code>` → `302` with `location == url` (AC-10). The older `test_create_link_returns_code_and_short_url` and `test_follow_link_*` tests stay as they are (P-3).
  - `test_parallel_follows_lose_no_click` — 50 `GET /<code>` calls through a `ThreadPoolExecutor(max_workers=10)`; count `== 50` (edge case).
  - `test_clicks_log_cannot_forge_lines` — `GET /links/abc%0AINFO:app.main:x/clicks` → `404`; exactly one `app.main` message, with no `\n` (edge case).
  - Note (P-14): after T-1 these tests pass on the first run, because T-1 already gives the behaviour. They fail if a later change counts `HEAD` or `404`, adds fields or logs headers. `test_parallel_follows_lose_no_click` can also pass without the lock: a race is not certain in one run. The lock is the real guard; review must check it.
- Smoke first: `::test_ac_4_unknown_code_no_count`, `::test_ac_7_body_has_only_code_and_clicks` (body keys only; smoke cannot read the container logs), `::test_ac_8_head_no_count`, `::test_ac_10_post_and_follow_same_shape`.
- Done when: the new tests pass; T-1 and older tests still pass; `pytest` and lint are green.

### T-3 Document the clicks endpoint
- Covers: AC-9. P-12.
- Files:
  - `README.md` (change) — after the `GET /{code}` block (`README.md:15-20`), add a `GET /links/{code}/clicks` bullet: `200 {"code": "<code>", "clicks": <n>}`, `404 {"detail": "Short link not found"}`; one line: a click is a `GET /{code}` that returns `302`, `HEAD` does not count. Change `README.md:22` to say short links **and their counts** are lost when the app restarts.
  - `tests/test_docs.py` (change) — pattern from `_readme_follow_link_block` and `test_readme_states_location_encoding`.
- Test first: `tests/test_docs.py::test_readme_documents_clicks_endpoint` — the README block that starts with `` - `GET /links/{code}/clicks` `` contains `200`, `"clicks"`, `404` and `Short link not found`; and some README line contains both `count` and `restart` (AC-9). Fails today.
- Done when: the doc test passes; the older doc tests in `tests/test_docs.py` still pass (see "Doc check" below); `pytest` and lint are green.

## Traceability
| AC    | Tasks | Tests |
|-------|-------|-------|
| AC-1  | T-1 | `tests/test_links.py::test_new_link_has_zero_clicks`, `smoke/test_5_count_short_link_clicks.py::test_ac_1_new_link_zero_clicks` |
| AC-2  | T-1 | `tests/test_links.py::test_each_follow_adds_one_click`, `smoke/test_5_count_short_link_clicks.py::test_ac_2_three_follows_three_clicks` |
| AC-3  | T-1 | `tests/test_links.py::test_clicks_counted_per_link`, `smoke/test_5_count_short_link_clicks.py::test_ac_3_counts_per_link` |
| AC-4  | T-2 | `tests/test_links.py::test_unknown_code_follow_does_not_change_count`, `smoke/test_5_count_short_link_clicks.py::test_ac_4_unknown_code_no_count` |
| AC-5  | T-1 | `tests/test_links.py::test_clicks_of_unknown_code_returns_404`, `smoke/test_5_count_short_link_clicks.py::test_ac_5_unknown_code_404` |
| AC-6  | T-1 | `tests/test_links.py::test_reading_clicks_does_not_add_clicks`, `smoke/test_5_count_short_link_clicks.py::test_ac_6_read_does_not_count` |
| AC-7  | T-2 | `tests/test_links.py::test_clicks_store_and_log_no_visitor_data`, `smoke/test_5_count_short_link_clicks.py::test_ac_7_body_has_only_code_and_clicks` (body only) |
| AC-8  | T-2 | `tests/test_links.py::test_head_does_not_count`, `smoke/test_5_count_short_link_clicks.py::test_ac_8_head_no_count` |
| AC-9  | T-3 | `tests/test_docs.py::test_readme_documents_clicks_endpoint` |
| AC-10 | T-2 | `tests/test_links.py::test_post_and_follow_responses_keep_their_shape`, existing `tests/test_links.py::test_create_link_returns_code_and_short_url`, `smoke/test_5_count_short_link_clicks.py::test_ac_10_post_and_follow_same_shape` |

## Risks and rollback
- **Lost clicks under load.** Without the lock, parallel `302`s can lose counts. The test may not catch a missing lock (see T-2 note), so the lock is a review point.
- **`HEAD` behaviour comes from FastAPI.** If a FastAPI upgrade starts to route `HEAD` to `GET` endpoints, `follow_link` would run for `HEAD` and count it. `test_head_does_not_count` fails then; the fix is a method check in `follow_link`, not a weaker test (P-3).
- **Memory.** One `int` per link, removed on restart like the links (spec A-5). No new growth beyond the existing `links` dict.
- **Doc check.** The older word check in `tests/test_docs.py:37` scans `README.md` and `docs/**`. A new README or doc line that names the 302 header together with a word from `CLAIMS` (`tests/test_docs.py:6`) fails it; reword the line, do not weaken the test (P-3).
- **Rollback.** Additive change, no data or config. Revert the feature commits; the endpoint and counts go away, other responses stay the same.
