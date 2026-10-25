# Spec: Count clicks on a short link

Feature: 5-count-short-link-clicks · PRD: #5 · Verdict: pass

## Problem
People who create a short link cannot see if anyone uses it. The app creates links and
redirects, but keeps no record of how often a link is followed. So a busy link and a dead
link look the same.

## Scope
### In
- Count every successful redirect (`302`) of a short link, repeat visits included.
- Read the total click count of a short link by its code, without any login.
- A clear `404` when asking for the count of an unknown code.
### Out
- Unique visitors (needs personal data).
- Counts per day, time of last click, referrer or other details.
- Limiting who can see the count (no owners or accounts).
- Counts that survive a restart (short links do not survive a restart either).
- Filtering out bots.
- Counting `HEAD` requests (A-3).
- Resetting or changing a count by hand.
- A list of counts for all links.

## Acceptance criteria
- **AC-1** Given a short link was just created, When a client sends `GET /links/<code>/clicks`,
  Then the response is `200` with `{"code": "<code>", "clicks": 0}`.
- **AC-2** Given a new short link, When a client sends `GET /<code>` 3 times without following
  redirects (each response is `302`), Then `GET /links/<code>/clicks` returns `"clicks": 3`.
- **AC-3** Given two new short links A and B, When a client sends `GET /<code A>` 2 times,
  Then the count of A is `2` and the count of B is still `0`.
- **AC-4** Given a short link with count `1`, When a client sends `GET /doesnotexist` (an unknown
  code) and gets `404`, Then the count of the short link is still `1`.
- **AC-5** Given no short link was created with code `doesnotexist`, When a client sends
  `GET /links/doesnotexist/clicks`, Then the response is `404` with
  `{"detail": "Short link not found"}`.
- **AC-6** Given a short link with count `2`, When a client sends `GET /links/<code>/clicks`
  3 times, Then every response has `"clicks": 2`.
- **AC-7** Given a short link is followed with request headers `User-Agent: ac7-agent` and
  `X-Forwarded-For: 203.0.113.7`, When a client reads its count, Then the JSON body has only the
  keys `code` and `clicks`, and the app log lines written for the follow and the read contain
  neither `ac7-agent` nor `203.0.113.7`.
- **AC-8** Given a new short link, When a client sends `HEAD /<code>`, Then the count stays `0`.
- **AC-9** Given the feature is built, When a reader opens the README, Then it documents
  `GET /links/{code}/clicks` with its `200` and `404` responses, and that counts are lost on restart.
- **AC-10** Given a short link exists, When a client sends `POST /links` and `GET /<code>`, Then the
  responses are the same as before this feature: `POST /links` returns only `code` and `short_url`,
  and `GET /<code>` returns `302` with the same `Location`.

## Contract
- New: `GET /links/{code}/clicks`
  - `200`: `{"code": "<code>", "clicks": <integer ≥ 0>}`
  - `404`: `{"detail": "Short link not found"}`
- `GET /{code}`: response unchanged. A `302` now also adds one to the link's count.
- `POST /links`: unchanged. A new link starts with count `0`.
- `GET /health`: unchanged.

## Edge cases and errors
- Unknown code on `GET /{code}` → `404` as today; no count changes (AC-4).
- Unknown code on `GET /links/{code}/clicks` → `404 {"detail": "Short link not found"}` (AC-5).
- Many clients follow the same link at the same time → every `302` adds exactly one; no click is lost.
- `HEAD /{code}` → no count change (AC-8, A-3). Its response is not changed by this feature.
- App restart → all links and counts are gone; `GET /links/<code>/clicks` → `404`.
- Code with characters outside the code alphabet, for example `GET /links/a%0Ab/clicks` → `404`;
  the log line cannot be forged with a newline.

## Non-functional
- P-5: the code in the path is only used as a lookup key; nothing else is read from the request.
- P-6 / P-11: the count stores no visitor data. Logs for follow and read hold the code only, no IP
  address, user agent or long URL. A read of an unknown code is logged as a warning.
- P-8: unknown code gets a clear `404` JSON error.
- P-10: the change is additive. Existing responses of `POST /links` and `GET /{code}` stay the same (AC-10).
- P-12: the README documents the new endpoint (AC-9).

## Assumptions
- **A-1** The count is read at `GET /links/{code}/clicks` and returns `{"code", "clicks"}`. The PRD
  names no path. It sits under `/links`, next to `POST /links`, so it can never clash with a short code.
- **A-2** A click is a `GET /{code}` that returns `302`. The PRD says "every successful redirect".
- **A-3** `HEAD` does not count. The PRD leaves this open (Q-1). Link preview tools and link checkers
  send `HEAD` without a person following the link, and the goal is to see how often a link is
  really followed.
- **A-4** Smoke checks may create short links to `https://example.com/` and follow them. This is safe
  test data: links live in memory, point to a reserved domain, and nobody else reads their counts.
- **A-5** The count has no upper limit. It lives only while the app runs, so it cannot grow without end
  in practice.

## Open questions
- **Q-1** (non-blocking) Should `HEAD` requests count as clicks? This spec assumes no (A-3). If the
  answer is yes, it is a follow-up feature: it needs a decision on how `HEAD /{code}` responds.
