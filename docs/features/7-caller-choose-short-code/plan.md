# Plan: Let the caller choose the short code

Feature: 7-caller-choose-short-code · Spec: ./spec.md · Risk: medium — new contract: optional `code` field and new `409` on `POST /links`; additive, no auth, data migration or breaking change · Verdict: pass

## Commands
| Purpose | Command | Found in |
|---------|---------|----------|
| install | `pip install -r requirements-dev.txt` | `.github/workflows/ci.yml:21` |
| test    | `pytest` | `.github/workflows/ci.yml:25` |
| lint    | `ruff check . && ruff format --check .` | `.github/workflows/ci.yml:23` |
| run     | `uvicorn app.main:app --reload` | `README.md:34` |
| smoke   | `BASE_URL=http://localhost:8080 pytest smoke -v` | `.github/workflows/ci.yml:56`, `README.md:47` |

## Approach
- Add `code: str | None = Field(default=None, min_length=3, max_length=32)` to `LinkIn` (`app/main.py:29`), with a `check_code` validator next to `check_url`: `re.fullmatch(r"[A-Za-z0-9_-]+", code)` (explicit ASCII class, not `\w`, so `é` fails), then `code.lower() in RESERVED_CODES` → error. Pydantic v2 does not turn `123` into a string (the existing `url: 123` test proves it), and `None` keeps the default (A-1). Bad `url` and bad `code` fail in the same `422` (spec edge case), before the handler runs.
- In `create_link`, take a new `links_lock` around "pick code → check `code in links` → store". Taken code → `logger.warning("short code taken code=%s", code)` and `HTTPException(409, "Short code already taken")`. This makes two parallel requests for one free code give exactly one `201` (spec edge case). `new_code()` runs inside the same lock, so a random code can never take a chosen code that is being stored (AC-12).
- Lookups stay plain dict lookups, so all codes stay exact-case (AC-3, AC-5). No change to `follow_link` or `read_clicks`.
- The existing `422` handler (`app/main.py:64-69`) logs only `loc` and `type`, never the value, so a rejected code cannot forge log lines. Nothing to add.
- **Rejected:** a route-level check of the code in `create_link`. It would return a different `422` body than pydantic and need a second error path; the validator keeps one `422` shape for `url` and `code` (P-4).
- Unit tests share one in-memory app. Every test that needs a fixed code, other than the AC-1 test with literal `My-Docs`, adds a random suffix (`f"My-Docs-{secrets.token_hex(4)}"`), so tests do not collide with each other.

## Tasks
### T-1 Create a link with a valid, free chosen code
- Covers: AC-1, AC-2, AC-4, AC-5, AC-6, AC-7, AC-8, AC-10, AC-11. P-5, P-8, P-11.
- Files:
  - `app/main.py` (change) — `code` field and `check_code` validator, pattern from `check_url` (`app/main.py:32-44`); `links_lock = threading.Lock()` next to `clicks_lock` (`app/main.py:26`); `create_link` (`app/main.py:77-83`) uses `link.code` when set, else `new_code()`, all under `links_lock`; `409` path follows the `404` path in `follow_link` (`app/main.py:88-92`).
  - `tests/test_links.py` (change) — pattern from `test_create_link_returns_code_and_short_url`, `test_create_link_rejects_invalid_url` (parametrize) and `test_new_link_has_zero_clicks`; new helper `_create_with_code(url, code)` like `_create`.
  - `smoke/test_7_caller_choose_short_code.py` (new) — pattern from `smoke/test_5_count_short_link_clicks.py`, naming rule from `README.md:50-51`.
- Test first: `tests/test_links.py`:
  - `test_create_link_with_chosen_code` — `POST {"url": "https://example.com/docs", "code": "My-Docs"}` → `201`, body `== {"code": "My-Docs", "short_url": "http://testserver/My-Docs"}` (AC-1). The only test that uses the literal `My-Docs`.
  - `test_chosen_code_redirects_and_counts` — suffixed code; `GET /<code>` → `302`, `location == url`; clicks `== 1` (AC-2).
  - `test_taken_code_returns_409` — create code with URL A; again with URL B → `409`, body `== {"detail": "Short code already taken"}`; `GET /<code>` → `302` to A; clicks unchanged (AC-4; edge case "`409` never changes a link").
  - `test_taken_code_logs_code_not_url` — on the `409`, one `WARNING` from `app.main` that contains the code; `caplog.text` has no part of URL B (P-11).
  - `test_code_differing_in_case_is_a_new_link` — `My-Docs-<hex>` → A, then `my-docs-<hex>` → `201` with `"code": "my-docs-<hex>"`; each redirects to its own URL (AC-5).
  - `test_random_code_cannot_be_chosen` — `_create(A)`; `POST` with that code and URL B → `409`; random link still `302` to A (AC-6).
  - `test_chosen_code_length_limits` — parametrize: length 2 and 33 → `422`; length 3 and 32 → `201` (unique codes, built from `token_hex`) (AC-7).
  - `test_chosen_code_rejects_bad_characters` — parametrize `"ab c12"`, `"abc.12"`, `"abc/12"`, `"abcé12"`, `" abc12"`, `"abc12 "`, `"abc12\n"` → `422`, body has no `code`/`short_url`, `len(links)` unchanged (AC-8, A-3).
  - `test_chosen_code_empty_or_not_string` — `""` and `123` → `422`; `None` → `201` with a 7-char `[A-Za-z0-9]` code (AC-10, A-1).
  - `test_bad_url_with_valid_code_keeps_code_free` — bad URL + suffixed code → `422`; then valid URL + same code → `201` (edge case). Bad URL + bad code → one `422` (edge case).
  - `test_chosen_code_starts_with_zero_clicks` — clicks `== {"code": code, "clicks": 0}` (AC-11).
- Smoke first: `smoke/test_7_caller_choose_short_code.py::test_ac_1_chosen_code_created`, `::test_ac_2_chosen_code_redirects_and_counts`, `::test_ac_4_taken_code_409`, `::test_ac_5_other_case_is_new_link`, `::test_ac_6_random_code_taken_409`, `::test_ac_7_length_limits`, `::test_ac_8_bad_characters_422`, `::test_ac_10_empty_null_non_string`, `::test_ac_11_chosen_code_zero_clicks`. Safe live (spec A-4): codes `My-Docs-<token_hex(4)>`, URL `https://example.com/`, memory only. httpx does not follow redirects by default.
- Done when: the new tests pass; all existing tests pass unchanged; `pytest` and lint are green.

### T-2 Refuse reserved names
- Covers: AC-9. P-5.
- Files:
  - `app/main.py` (change) — `RESERVED_CODES = {"links", "health", "docs", "redoc"}` next to `CODE_ALPHABET`; `check_code` raises `ValueError` when `code.lower()` is in it.
  - `tests/test_links.py` (change) — same patterns as T-1.
  - `smoke/test_7_caller_choose_short_code.py` (change).
- Test first: `tests/test_links.py`:
  - `test_chosen_code_rejects_reserved_names` — parametrize `links`, `health`, `docs`, `redoc`, `Health`, `DOCS`, `Links`, `REDOC` → `422`; then `GET /health` → `200 {"status": "ok"}` and `GET /docs` → `200` (AC-9; edge case "differs only in case"). Fails today for the codes of 3+ characters.
  - `test_chosen_code_may_contain_reserved_name` — `docs-<hex>` and `my-health-<hex>` → `201` (edge case).
- Smoke first: `::test_ac_9_reserved_names_422` (creates nothing on success).
- Done when: the new tests pass; T-1 and older tests still pass; `pytest` and lint are green.

### T-3 Pin exact case, random codes and parallel creates
- Covers: AC-3, AC-12, AC-13. Spec edge case "two requests choose the same free code".
- Files:
  - `tests/test_links.py` (change) — log check pattern from `test_create_link_logs_code_not_url`; parallel pattern from `test_parallel_follows_lose_no_click`; `monkeypatch` on `app.main.secrets.choice`.
  - `smoke/test_7_caller_choose_short_code.py` (change).
- Test first: `tests/test_links.py`:
  - `test_chosen_code_other_case_is_404` — create `My-Docs-<hex>`; `GET /my-docs-<hex>` and `GET /links/my-docs-<hex>/clicks` → `404 {"detail": "Short link not found"}`; clicks of the real code stay `0` (AC-3).
  - `test_random_code_skips_chosen_code` — choose a 7-char code like `Ab1<4 hex>`; monkeypatch `secrets.choice` to give that code's characters first, then other characters; `POST` without `code` → `201` and the returned code `!=` the chosen one (AC-12).
  - `test_random_code_works_only_in_exact_case` — `_create`; body keys `== {"code", "short_url"}`, code matches `[A-Za-z0-9]{7}`; `GET /<code>.swapcase()` → `404` (skip the swap check only if the code has no letters) (AC-13).
  - `test_parallel_creates_of_one_code_give_one_201` — 20 `POST`s with the same suffixed code through `ThreadPoolExecutor(max_workers=10)`; statuses sorted `== [201] + [409] * 19` (edge case).
  - Note (P-14): after T-1 these tests pass on the first run. `new_code` already skips taken codes and T-1 adds the lock. They fail if a later change makes lookups case-insensitive or drops the "not in `links`" check. The parallel test can pass without the lock (a race is not certain in one run); review must check the lock.
- Smoke first: `::test_ac_3_other_case_404`, `::test_ac_12_random_codes_differ` (create a chosen code, then 5 random links; none equals any code seen), `::test_ac_13_only_url_same_as_before`.
- Done when: the new tests pass; older tests still pass; `pytest` and lint are green.

### T-4 Document the `code` field
- Covers: AC-14. P-12.
- Files:
  - `README.md` (change) — in the `POST /links` block (`README.md:11-14`): request shows `"code": "<optional>"`; one sub-bullet with the rules (3–32 characters, `A–Z a–z 0–9 - _`, not `links`/`health`/`docs`/`redoc` in any case), that codes are case-sensitive and saved as sent; add `409 {"detail": "Short code already taken"}`; extend the `422` line with "or `code` breaks the rules or is a reserved name".
  - `tests/test_docs.py` (change) — new `_readme_create_link_block()`, pattern from `_readme_clicks_block` (`tests/test_docs.py:20-32`).
- Test first: `tests/test_docs.py::test_readme_documents_chosen_code` — the block that starts with `` - `POST /links` `` contains `"code"`, `3`, `32`, `case-sensitive`, `409`, `Short code already taken`, `422`, and each of `links`, `health`, `docs`, `redoc` (AC-14). Fails today.
- Done when: the doc test passes; the older doc tests still pass (see "Doc check" below); `pytest` and lint are green.

## Traceability
| AC    | Tasks | Tests |
|-------|-------|-------|
| AC-1  | T-1 | `tests/test_links.py::test_create_link_with_chosen_code`, `smoke/test_7_caller_choose_short_code.py::test_ac_1_chosen_code_created` |
| AC-2  | T-1 | `tests/test_links.py::test_chosen_code_redirects_and_counts`, `smoke/test_7_caller_choose_short_code.py::test_ac_2_chosen_code_redirects_and_counts` |
| AC-3  | T-3 | `tests/test_links.py::test_chosen_code_other_case_is_404`, `smoke/test_7_caller_choose_short_code.py::test_ac_3_other_case_404` |
| AC-4  | T-1 | `tests/test_links.py::test_taken_code_returns_409`, `smoke/test_7_caller_choose_short_code.py::test_ac_4_taken_code_409` |
| AC-5  | T-1 | `tests/test_links.py::test_code_differing_in_case_is_a_new_link`, `smoke/test_7_caller_choose_short_code.py::test_ac_5_other_case_is_new_link` |
| AC-6  | T-1 | `tests/test_links.py::test_random_code_cannot_be_chosen`, `smoke/test_7_caller_choose_short_code.py::test_ac_6_random_code_taken_409` |
| AC-7  | T-1 | `tests/test_links.py::test_chosen_code_length_limits`, `smoke/test_7_caller_choose_short_code.py::test_ac_7_length_limits` |
| AC-8  | T-1 | `tests/test_links.py::test_chosen_code_rejects_bad_characters`, `smoke/test_7_caller_choose_short_code.py::test_ac_8_bad_characters_422` |
| AC-9  | T-2 | `tests/test_links.py::test_chosen_code_rejects_reserved_names`, `smoke/test_7_caller_choose_short_code.py::test_ac_9_reserved_names_422` |
| AC-10 | T-1 | `tests/test_links.py::test_chosen_code_empty_or_not_string`, `smoke/test_7_caller_choose_short_code.py::test_ac_10_empty_null_non_string` |
| AC-11 | T-1 | `tests/test_links.py::test_chosen_code_starts_with_zero_clicks`, `smoke/test_7_caller_choose_short_code.py::test_ac_11_chosen_code_zero_clicks` |
| AC-12 | T-3 | `tests/test_links.py::test_random_code_skips_chosen_code`, `smoke/test_7_caller_choose_short_code.py::test_ac_12_random_codes_differ` |
| AC-13 | T-3 | `tests/test_links.py::test_random_code_works_only_in_exact_case`, existing `tests/test_links.py::test_create_link_returns_code_and_short_url`, `smoke/test_7_caller_choose_short_code.py::test_ac_13_only_url_same_as_before` |
| AC-14 | T-4 | `tests/test_docs.py::test_readme_documents_chosen_code` |

## Risks and rollback
- **Race on create.** Without `links_lock`, two parallel creates of one code can both get `201` and the second overwrites the first link. The parallel test may not catch a missing lock (T-3 note), so the lock is a review point.
- **Shared test state.** Unit tests share the global `links` dict. A new test that reuses a fixed code gets `409`. Use a random suffix; only the AC-1 test uses the literal `My-Docs`.
- **Smoke reruns.** Smoke codes carry a random suffix (spec A-4), so a second run against the same app does not hit `409`.
- **New routes later.** A future one-segment route (for example `/stats`) would hide a chosen code with that name. Such a feature must add its name to `RESERVED_CODES`; out of scope here.
- **Doc check.** The word check in `tests/test_docs.py:63` flags any line in `README.md` or `docs/**` that has `location` or `redirect` and also `exactly`, `as sent` or `unchanged`, unless it says `encod`. So the README line about how codes are saved must not name the 302 header or the word for following a link; reword, do not weaken the test (P-3).
- **Rollback.** Additive change, no data or config. Revert the feature commits; `code` is then ignored by pydantic (extra fields are allowed) and every link gets a random code again.
