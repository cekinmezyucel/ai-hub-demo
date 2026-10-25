# Spec: Let the caller choose the short code

Feature: 7-caller-choose-short-code · PRD: #7 · Verdict: pass

## Problem
Today every short link gets a random code. API callers cannot know a link before it exists,
so they cannot plan for it, for example in printed material or docs written in advance.
They also cannot get a link that says what it points to.

## Scope
### In
- An optional `code` field on `POST /links`, for a code the caller chooses.
- Rules for a chosen code: 3–32 characters, only ASCII letters, digits, `-` and `_`.
- Chosen codes are case-sensitive, like random codes, and saved exactly as sent.
- `409` when the chosen code is already taken in the exact same case (chosen or random).
- `422` when the chosen code breaks the rules or is a reserved path in any case.
- Random codes never match an existing code.
- README documents the `code` field, the case rule, `409` and `422`.
### Out
- Case-insensitive matching for any code, chosen or random.
- Changing or deleting a code after it is created.
- Reserving or owning codes per user (there is no login).
- Suggesting a free code when the chosen one is taken.
- Keeping links over a restart (they stay in memory).

## Acceptance criteria
- **AC-1** Given no link with code `My-Docs` exists, When a client sends `POST /links` with
  `{"url": "https://example.com/docs", "code": "My-Docs"}`, Then the response is `201` with
  `"code": "My-Docs"` and a `short_url` that ends in `/My-Docs`.
- **AC-2** Given `My-Docs` was created for `https://example.com/docs`, When a client sends
  `GET /My-Docs` once, Then the response is `302` with `Location: https://example.com/docs`,
  and `GET /links/My-Docs/clicks` returns `200` with `"clicks": 1`.
- **AC-3** Given only `My-Docs` exists, When a client sends `GET /my-docs` and
  `GET /links/my-docs/clicks`, Then both responses are `404` with `{"detail": "Short link not found"}`,
  and the click count of `My-Docs` does not change.
- **AC-4** Given `My-Docs` exists for URL A, When a client sends `POST /links` with code `My-Docs`
  and URL B, Then the response is `409` with `{"detail": "Short code already taken"}` (A-2), and
  `GET /My-Docs` still returns `302` to URL A.
- **AC-5** Given `My-Docs` exists for URL A, When a client sends `POST /links` with code `my-docs`
  and URL B, Then the response is `201` with `"code": "my-docs"`, `GET /My-Docs` redirects to A,
  and `GET /my-docs` redirects to B.
- **AC-6** Given a link with a random code (for example `AbC123x`) exists, When a client sends
  `POST /links` with that exact code, Then the response is `409`, and the random link still
  redirects to its first URL.
- **AC-7** Given a valid URL, When a client sends `POST /links` with a code of 2 or 33 allowed
  characters, Then the response is `422`; with a code of 3 or 32 allowed characters, it is `201`.
- **AC-8** Given a valid URL, When a client sends `POST /links` with a code that contains any other
  character (for example a space, `.`, `/`, `é`, or a leading or trailing space), Then the response
  is `422` and no link is created.
- **AC-9** Given a valid URL, When a client sends `POST /links` with code `links`, `health`, `docs`,
  `redoc`, `Health` or `DOCS`, Then the response is `422`, and `GET /health` and `GET /docs` work
  as before.
- **AC-10** Given a valid URL, When a client sends `POST /links` with code `""` (empty), `null`
  or a non-string value such as `123`, Then: `""` and `123` give `422`; `null` is treated as no
  code and gives `201` with a random code (A-1).
- **AC-11** Given a code was chosen, When the link is created, Then
  `GET /links/<code>/clicks` returns `"clicks": 0`.
- **AC-12** Given links with chosen codes exist, When a client creates links without `code`,
  Then every new random code differs from every existing code.
- **AC-13** Given any valid URL, When a client sends `POST /links` with only `url`, Then the
  response is `201` with only `code` and `short_url`, the code is 7 ASCII letters or digits, and
  it works only in its exact case — same as before this feature.
- **AC-14** Given the feature is built, When a reader opens the README, Then it documents the
  optional `code` field and its rules, that codes are case-sensitive and saved as sent, the `409`
  case and the `422` cases (bad code and reserved names).

## Contract
- `POST /links` request body: `{"url": "<as today>", "code": "<optional>"}`
  - `code`: optional string, 3–32 characters from `A–Z a–z 0–9 - _`. Saved exactly as sent.
    Not one of `links`, `health`, `docs`, `redoc`, compared in any case.
- `POST /links` responses:
  - `201 {"code": "<code>", "short_url": "<base URL>/<code>"}` — unchanged shape. With `code`,
    the returned code is the chosen code exactly as sent.
  - `409 {"detail": "Short code already taken"}` — new. The code exists in the exact same case.
  - `422 {"detail": ...}` — as today for `url`; now also for a bad or reserved `code`.
- `GET /{code}` and `GET /links/{code}/clicks`: unchanged. Exact-case lookup for all codes.
- `GET /health`, `GET /docs`, `GET /redoc`: unchanged.

## Edge cases and errors
- Both `url` and `code` are bad → `422` (one response, no link created).
- Valid code but bad `url` → `422`, the code stays free.
- Two requests choose the same free code at the same time → exactly one `201`, the other `409`.
- Code differs from a reserved name only in case (`Links`, `REDOC`) → `422`.
- Code that contains a reserved name (`docs-2026`, `my-health`) → allowed, `201`.
- `code` is `null` → same as no `code` (A-1).
- `409` and `422` never change any existing link or click count.
- A rejected code is logged without forging log lines (newlines escaped), as for unknown codes today.

## Non-functional
- P-5: `code` is checked against the rules before it is stored or used in a path. Only the
  allowed characters ever reach `short_url` or a lookup.
- P-8: `409` and `422` return clear JSON errors.
- P-10: the change is additive. Callers that send only `url` get the same response as today, and
  existing random links keep working (AC-13).
- P-11: a create with a chosen code and a `409` are logged with the code only; no URL, IP address
  or user agent.
- P-12: README documents the new field and errors (AC-14).

## Assumptions
- **A-1** `"code": null` means "no code" and gives a random code. The PRD says `code` is optional;
  JSON clients often send `null` for an unset field.
- **A-2** The `409` body is `{"detail": "Short code already taken"}`. The PRD names only the status;
  this matches the `{"detail": ...}` shape of the existing `404`.
- **A-3** The code is not trimmed: a leading or trailing space makes it invalid (`422`). The PRD says
  the code is saved exactly as sent, and the URL is not trimmed either.
- **A-4** Smoke checks may create links with chosen codes that carry a random suffix, pointing to
  `https://example.com/`. Fixed codes like `My-Docs` would give `409` on the second run against the
  same running app.
- **A-5** The example random code `AbC123` in the PRD has 6 characters; real random codes have 7.
  AC-6 uses a real random code from a `POST /links` response.

## Open questions
- None.
