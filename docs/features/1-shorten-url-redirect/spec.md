# Spec: Shorten a URL and redirect to it

Feature: 1-shorten-url-redirect · PRD: #1 · Verdict: pass

## Problem
Developers and scripts that call ai-hub-demo cannot turn a long URL into a short link.
They have to pass the full URL around, which is hard to share and type.

## Scope
### In
- Create a short link for an absolute `http` or `https` URL of at most 2,048 characters.
- Follow a short link: redirect to the original URL.
- Clear errors for invalid input and for unknown short links.
### Out
- Links that survive an app restart.
- Custom aliases chosen by the client.
- Link expiry and deleting links.
- Click counts or other stats.
- Users, login and rate limits.
- A web page or UI.
- Returning the same short link for a URL that was shortened before.

## Acceptance criteria
- **AC-1** Given the service is running, When a client sends `POST /links` with `{"url": "https://example.com/some/long/path?x=1"}`,
  Then the response is `201` with a JSON body that has a `code` and a `short_url`, and `short_url` ends with `/<code>`.
- **AC-2** Given a short link was created for `https://example.com/some/long/path?x=1`, When a client sends `GET /<code>`
  without following redirects, Then the response is `302` and the `Location` header is exactly `https://example.com/some/long/path?x=1` (this URL has no character that gets percent-encoded; see feature 3-redirect-location-exact-url).
- **AC-3** Given the service is running, When a client sends `POST /links` with `url` set to `javascript:alert(1)`,
  `ftp://example.com`, `/relative/path`, `https://` (no host) or `""`, or with no `url` field,
  Then the response is `422` with a JSON error body and no `code` or `short_url`.
- **AC-4** Given the service is running, When a client sends `POST /links` with a valid `https` URL of exactly 2,048 characters,
  Then the response is `201`; and When the URL has 2,049 characters, Then the response is `422` with a JSON error body.
- **AC-5** Given the service is running, When a client sends `POST /links` twice with the same URL,
  Then both responses are `201` with different `code` values, and `GET /<code>` for each one redirects to that URL.
- **AC-6** Given no short link was created with code `doesnotexist`, When a client sends `GET /doesnotexist`,
  Then the response is `404` with a JSON error body and no `Location` header.

## Contract
- `POST /links`
  - Request: `{"url": "<absolute http(s) URL, 1–2,048 characters>"}`
  - `201`: `{"code": "<code>", "short_url": "<base URL>/<code>"}`
  - `422`: `{"detail": ...}`: invalid or missing `url`
- `GET /{code}`
  - `302` with `Location: <original URL>` (percent-encoded; see feature 3-redirect-location-exact-url)
  - `404`: `{"detail": "Short link not found"}`
- `GET /health`: unchanged.

## Edge cases and errors
- URL with query string and fragment → stored as sent and kept in `Location` (`Location` is percent-encoded; see feature 3-redirect-location-exact-url).
- URL with leading or trailing spaces → `422`; the service does not trim it (A-4).
- Scheme in upper case (`HTTPS://example.com`) → accepted; `Location` is the URL as sent (`Location` is percent-encoded; see feature 3-redirect-location-exact-url).
- Request body is not JSON, or `url` is not a string → `422`.
- A code never equals an existing path: `health`, `links`, `docs`, `redoc`, `openapi.json`.
- `GET /<code>` with a code that has the right format but was never created → `404` (AC-6).
- App restart → all short links are gone; `GET /<code>` → `404` (Out of scope: links that survive a restart).

## Non-functional
- P-5: only absolute `http`/`https` URLs with a host are stored, so the redirect cannot send a client to `javascript:` or another scheme.
- P-8: every rejected request gets a clear `422` or `404` JSON error.
- P-11: creating a link and every error are logged with the code. The long URL is not logged: it can hold personal data or tokens in its query.
- P-12: the README documents `POST /links` and `GET /{code}`.

## Assumptions
- **A-1** The redirect is `302`, not `301`. Links are not permanent (they are lost on restart), and browsers cache `301` for a long time.
- **A-2** A code is 7 characters of `A–Z`, `a–z` and `0–9`, chosen at random. Enough for a demo; the PRD does not set a format.
- **A-3** `short_url` is built from the base URL of the incoming request. The PRD does not name a public domain.
- **A-4** The URL is checked as sent: no trimming, no normalising. The PRD says "exactly" for the redirect target (`Location` is percent-encoded; see feature 3-redirect-location-exact-url).
- **A-5** No limit on the number of stored links. Rate limits are out of scope, and links live only while the app runs.

## Open questions
None.
