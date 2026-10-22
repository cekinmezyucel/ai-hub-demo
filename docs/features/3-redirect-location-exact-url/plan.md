# Plan: Redirect Location is not exactly the URL as sent

Feature: 3-redirect-location-exact-url · Spec: ./spec.md · Risk: low — tests and docs only, no code behaviour or contract change · Verdict: pass

## Commands
| Purpose | Command | Found in |
|---------|---------|----------|
| install | `pip install -r requirements-dev.txt` | `.github/workflows/ci.yml:21` |
| test    | `pytest` | `.github/workflows/ci.yml:25` |
| lint    | `ruff check . && ruff format --check .` | `.github/workflows/ci.yml:23` |
| run     | `uvicorn app.main:app --reload` | `README.md:27` |
| smoke   | `BASE_URL=http://localhost:8080 pytest smoke -v` | `.github/workflows/ci.yml:56`, `README.md:40` |

## Approach
- No change to `app/main.py` behaviour (spec P-2). `RedirectResponse` in Starlette already gives the encoding in the Contract; T-1 pins it with tests so a later change cannot alter it silently.
- The docs fix is guarded by a small doc check in pytest (`tests/test_docs.py`), so `verify` can run AC-4 and AC-5 with the normal `pytest` command (P-1).
- Feature 1's `spec.md` and `plan.md` lines are corrected in place with a short note that points to this feature, not deleted (spec A-1).
- README line "The URL is stored exactly as sent" stays: it is about storage, which is true (spec A-3).
- **Rejected:** a manual `grep` in the PR as the only AC-5 check. It is not repeatable, and the next doc change could bring the claim back without any test failing.

## Tasks
### T-1 Pin today's `Location` encoding with tests
- Covers: AC-1, AC-2, AC-3, AC-6. Edge case "stray `%`" (spec A-2).
- Files:
  - `tests/test_links.py` (change) — pattern from `tests/test_links.py::test_follow_link_redirects_to_url` (uses `_create`, `follow_redirects=False`).
  - `smoke/test_3_redirect_location_exact_url.py` (new) — pattern from `smoke/test_1_shorten_url_redirect.py`, naming rule from `README.md:43-44`.
- Test first: `tests/test_links.py`:
  - `test_follow_link_encodes_unsafe_chars` — create `https://example.com/a|b?q={x}&r="y"`; `GET /<code>` → `302`, `Location == "https://example.com/a%7Cb?q=%7Bx%7D&r=%22y%22"` (AC-1).
  - `test_follow_link_encodes_non_ascii` — `POST /links` `https://example.com/café` → `201`; `GET /<code>` → `302`, `Location == "https://example.com/caf%C3%A9"` (AC-2).
  - `test_follow_link_does_not_encode_twice` — create `https://example.com/p%20q/r?s=1&t=a:b@c#frag`; `Location` equals that URL (AC-3).
  - `test_follow_link_keeps_stray_percent` — create `https://example.com/100%` → `201`; `Location == "https://example.com/100%"` (edge case, A-2).
  - `test_create_link_accepts_encodable_urls` (parametrized: the four URLs above) — each `POST /links` → `201` (AC-6).
  - The existing `test_create_link_rejects_invalid_url`, `test_create_link_accepts_*` and `test_follow_link_*` tests stay unchanged (AC-6, P-3).
  - Note (P-14): these tests pass on the first run, because they pin existing behaviour. They fail if the encoding or the `POST /links` checks change.
- Smoke first: `smoke/test_3_redirect_location_exact_url.py::test_ac_1_unsafe_chars_encoded`, `::test_ac_2_non_ascii_encoded`, `::test_ac_3_safe_url_unchanged`, `::test_ac_6_same_urls_accepted` (`POST` of the AC-1/2/3 URLs → `201`; `javascript:alert(1)` → `422`). Safe live: same as feature 1 — the v0 app runs inside the CI job, keeps links in memory only and is removed after the job; test data uses the reserved domain `example.com`. httpx does not follow redirects by default. AC-4 and AC-5 are about docs, so they get no smoke check.
- Done when: the new tests pass; all existing tests pass unchanged; `pytest` and lint are green.

### T-2 Correct the docs and comments about `Location`
- Covers: AC-4, AC-5. P-12 (README in the same PR).
- Files:
  - `tests/test_docs.py` (new) — pattern from `tests/test_health.py` (plain module, `test_` functions, no fixtures). Read files with `pathlib.Path(__file__).parent.parent` as the repo root.
  - `README.md` (change) — `README.md:16`: replace `Location: <original URL>` with the rule: `Location` is the stored URL, UTF-8 percent-encoded except letters, digits, `-._~` and `:/%#?=@[]!$&'()*+,;`. Examples: `|` → `%7C`, `{` → `%7B`, `é` → `%C3%A9`. Note that `%` is kept, so an encoded URL is not encoded twice. Keep `README.md:14` (spec A-3).
  - `app/main.py` (change, comment only) — `app/main.py:30`: drop "the redirect returns it exactly"; say the URL is stored as sent and the redirect percent-encodes unsafe characters.
  - `docs/features/1-shorten-url-redirect/spec.md` (change) — lines 27 (AC-2), 44 (Contract `<original URL>`), 49, 51 and 67 (A-4): keep the text, add a short note such as "(`Location` is percent-encoded; see feature 3-redirect-location-exact-url)", or reword so it no longer claims "exactly as sent".
  - `docs/features/1-shorten-url-redirect/plan.md` (change) — lines 17, 50 and 52: same kind of note.
- Test first: `tests/test_docs.py`:
  - `test_readme_states_location_encoding` — the README `GET /{code}` bullet block (from the line starting `` - `GET /{code}` `` to the next blank line) contains `percent-encoded` and at least one of `%7C`, `%7B`, `%C3%A9`; and it contains neither `exactly as sent` nor `<original URL>` (AC-4). Fails today.
  - `test_no_doc_says_location_is_url_as_sent` — scan `README.md`, `docs/**/*.md` (skip `docs/features/3-redirect-location-exact-url/`, which describes the bug) and `app/**/*.py`. A line fails when it mentions `Location` or `redirect` (case-insensitive) **and** one of `exactly`, `as sent`, `unchanged`, `<original URL>`, **unless** it also mentions `encod` (AC-5). The failure message lists `path:line`. Fails today on the lines named above.
- Done when: both doc tests pass; T-1 tests still pass; `pytest` and lint are green; `grep -rn "exactly as sent" README.md app docs/features/1-shorten-url-redirect` shows no line about `Location`.

## Traceability
| AC   | Tasks | Tests |
|------|-------|-------|
| AC-1 | T-1 | `tests/test_links.py::test_follow_link_encodes_unsafe_chars`, `smoke/test_3_redirect_location_exact_url.py::test_ac_1_unsafe_chars_encoded` |
| AC-2 | T-1 | `tests/test_links.py::test_follow_link_encodes_non_ascii`, `smoke/test_3_redirect_location_exact_url.py::test_ac_2_non_ascii_encoded` |
| AC-3 | T-1 | `tests/test_links.py::test_follow_link_does_not_encode_twice`, `smoke/test_3_redirect_location_exact_url.py::test_ac_3_safe_url_unchanged` |
| AC-4 | T-2 | `tests/test_docs.py::test_readme_states_location_encoding` |
| AC-5 | T-2 | `tests/test_docs.py::test_no_doc_says_location_is_url_as_sent` |
| AC-6 | T-1 | `tests/test_links.py::test_create_link_accepts_encodable_urls`, existing `tests/test_links.py::test_create_link_rejects_invalid_url`, `smoke/test_3_redirect_location_exact_url.py::test_ac_6_same_urls_accepted` |

## Risks and rollback
- **Starlette upgrade.** The encoding comes from Starlette's `RedirectResponse`, not from our code. A version bump that changes the safe set breaks T-1 tests. That is the purpose of the tests: it would be a contract change and needs a spec.
- **Doc check is a heuristic.** `test_no_doc_says_location_is_url_as_sent` matches words, so a later true sentence can trip it (for example "redirect status is unchanged"). Fix by rewording the doc line, not by weakening the test (P-3).
- **Changing a shipped spec.** Feature 1's spec and plan are history. T-2 only adds notes or rewords the claim; acceptance criteria keep their meaning (spec A-1).
- **Rollback.** No code behaviour, data or config changes. Revert the feature commits.
