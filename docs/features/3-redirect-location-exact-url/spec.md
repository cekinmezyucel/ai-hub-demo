# Spec: Redirect Location is not exactly the URL as sent

Feature: 3-redirect-location-exact-url · PRD: #3 · Verdict: pass

## Problem
`GET /{code}` answers `302` with a `Location` header. For some characters that `POST /links`
accepts (for example `|`, `{`, `"`, `é`), `Location` is percent-encoded. The README and other
project docs say the URL comes back "exactly as sent". API clients that trust the docs see a
mismatch. The behaviour stays; the docs must describe it.

## Scope
### In
- Keep today's `Location` behaviour of `GET /{code}` and pin it with tests (PRD req. 1).
- README API section: a short encoding rule for `Location` with examples such as `|`, `{`, `é` (PRD req. 2).
- Remove every claim in project docs and code comments that `Location` is the URL "exactly as sent":
  README, the code comment on URL checks, and feature 1's spec (A-4 and its edge case line) (PRD req. 3).
- `POST /links` keeps accepting the same URLs (PRD req. 4).

### Out
- Changing the code so `Location` is the stored URL unchanged (options A1 / A2 of the earlier spec Q-1).
- Rejecting non-ASCII URLs in `POST /links`.
- Any other change to the `POST /links` checks or to URL normalising.
- Changing the `302` status or the `404` behaviour.
- Listing every encoded character in the README.

## Acceptance criteria
- **AC-1** Given a link created with `POST /links` for `https://example.com/a|b?q={x}&r="y"`,
  When a client sends `GET /<code>` without following redirects,
  Then the response is `302` and `Location` is exactly `https://example.com/a%7Cb?q=%7Bx%7D&r=%22y%22`.
- **AC-2** Given `POST /links` with `{"url": "https://example.com/café"}`,
  When the request is sent,
  Then the response is `201`; and When a client sends `GET /<code>` for the returned code,
  Then the response is `302` and `Location` is exactly `https://example.com/caf%C3%A9`.
- **AC-3** Given a link for a URL with only safe characters, `https://example.com/p%20q/r?s=1&t=a:b@c#frag`,
  When a client sends `GET /<code>`,
  Then the response is `302` and `Location` is exactly `https://example.com/p%20q/r?s=1&t=a:b@c#frag`
  (an existing `%` escape is not encoded again).
- **AC-4** Given the README API section,
  When a reader looks at `GET /{code}`,
  Then it states the encoding rule for `Location` with at least one example of an encoded character,
  and it does not say `Location` is the URL "exactly as sent".
- **AC-5** Given all project docs and code comments (README, `docs/`, source comments),
  When they are searched for claims about `Location` or the redirect target,
  Then none says it is the URL "exactly as sent" or unchanged.
- **AC-6** Given the URLs accepted and rejected by `POST /links` today (including the existing tests),
  When they are sent after this change,
  Then each gets the same status (`201` or `422`) as before.

## Contract
No change to the API. This spec only writes down today's `GET /{code}` behaviour:

- `302`, `Location` = the stored URL, UTF-8 percent-encoded, except for these characters,
  which stay unchanged: ASCII letters and digits, `-._~`, and `:/%#?=@[]!$&'()*+,;`.
- Examples: `|` → `%7C`, `{` → `%7B`, `}` → `%7D`, `"` → `%22`, `é` → `%C3%A9`.
- `%` stays unchanged, so an already encoded URL is not encoded twice.
- The stored URL itself is still kept as sent: no trimming, no normalising.

## Edge cases and errors
- URL that is already percent-encoded (`%20`) → `Location` keeps it as is (AC-3).
- URL with a stray `%` not followed by two hex digits (for example `https://example.com/100%`) →
  accepted as today; `Location` keeps the `%` unchanged (A-2).
- URL with only safe characters, query and fragment → `Location` equals the URL (AC-3).
- Non-ASCII URL → accepted as today (`201`); `Location` holds the UTF-8 percent-encoded form (AC-2).
- Unknown code → `404 {"detail": "Short link not found"}`, unchanged.

## Non-functional
- P-1: every AC is checked by a test against the HTTP API or by a doc check.
- P-2: docs and tests only; no code behaviour change.
- P-10: no change to the API; the change makes the docs match what clients already get.
- P-12: README changes in the same PR.

## Assumptions
- **A-1** Feature 1's `spec.md` and `plan.md` are project docs for AC-5. Their lines that say
  `Location` is the URL "exactly as sent" are corrected (for example with a short note that points
  to this feature), not deleted. (PRD req. 3 names A-4 of feature 1; the edge case line next to it
  makes the same claim.)
- **A-2** The safe set in the Contract is today's behaviour, taken from the running code, not a new
  rule. A stray `%` is kept as is, as today. (PRD req. 1 says "keeps today's behaviour".)
- **A-3** README line "The URL is stored exactly as sent" may stay if it is clear that it is about
  storage, not `Location`. (Storage really is unchanged; only `Location` is encoded.)

## Open questions
- none
