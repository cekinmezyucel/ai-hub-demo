import re
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app, links

client = TestClient(app)


def test_create_link_returns_code_and_short_url():
    response = client.post("/links", json={"url": "https://example.com/some/long/path?x=1"})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"code", "short_url"}
    assert re.fullmatch(r"[A-Za-z0-9]{7}", body["code"])
    assert body["short_url"] == "http://testserver/" + body["code"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com",
        "/relative/path",
        "https://",
        "",
        " https://example.com",
        "https://example.com ",
        123,
    ],
)
def test_create_link_rejects_invalid_url(url):
    response = client.post("/links", json={"url": url})

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "code" not in body
    assert "short_url" not in body


def test_create_link_rejects_missing_url():
    response = client.post("/links", json={})

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "code" not in body
    assert "short_url" not in body


def test_create_link_rejects_non_json_body():
    response = client.post(
        "/links", content=b"not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


def _url_of_length(n):
    prefix = "https://example.com/"
    return prefix + "a" * (n - len(prefix))


def test_create_link_accepts_2048_chars():
    url = _url_of_length(2048)
    assert len(url) == 2048

    response = client.post("/links", json={"url": url})

    assert response.status_code == 201


def test_create_link_rejects_2049_chars():
    url = _url_of_length(2049)
    assert len(url) == 2049

    response = client.post("/links", json={"url": url})

    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_link_accepts_upper_case_scheme():
    response = client.post("/links", json={"url": "HTTPS://example.com"})

    assert response.status_code == 201


def test_create_link_twice_gives_different_codes():
    url = "https://example.com/twice"

    first = client.post("/links", json={"url": url})
    second = client.post("/links", json={"url": url})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["code"] != second.json()["code"]


def test_create_link_logs_code_not_url(caplog):
    caplog.set_level("INFO")
    url = "https://example.com/?token=secret-value"

    response = client.post("/links", json={"url": url})

    assert response.status_code == 201
    assert response.json()["code"] in caplog.text
    assert "secret-value" not in caplog.text


def _create(url):
    response = client.post("/links", json={"url": url})
    assert response.status_code == 201
    return response.json()["code"]


def test_follow_link_redirects_to_url():
    url = "https://example.com/some/long/path?x=1"
    code = _create(url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url


def test_follow_link_keeps_query_and_fragment():
    url = "https://example.com/p?a=1&b=2#frag"
    code = _create(url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url


def test_follow_link_keeps_upper_case_scheme():
    url = "HTTPS://example.com"
    code = _create(url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url


def test_same_url_twice_both_codes_redirect():
    url = "https://example.com/same"
    first = _create(url)
    second = _create(url)

    for code in (first, second):
        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == url


def test_follow_link_encodes_unsafe_chars():
    code = _create('https://example.com/a|b?q={x}&r="y"')

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/a%7Cb?q=%7Bx%7D&r=%22y%22"


def test_follow_link_encodes_non_ascii():
    code = _create("https://example.com/café")

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/caf%C3%A9"


def test_follow_link_does_not_encode_twice():
    url = "https://example.com/p%20q/r?s=1&t=a:b@c#frag"
    code = _create(url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url


def test_follow_link_keeps_stray_percent():
    url = "https://example.com/100%"
    code = _create(url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url


@pytest.mark.parametrize(
    "url",
    [
        'https://example.com/a|b?q={x}&r="y"',
        "https://example.com/café",
        "https://example.com/p%20q/r?s=1&t=a:b@c#frag",
        "https://example.com/100%",
    ],
)
def test_create_link_accepts_encodable_urls(url):
    response = client.post("/links", json={"url": url})

    assert response.status_code == 201


def test_unknown_code_returns_404():
    response = client.get("/doesnotexist", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}
    assert "location" not in response.headers


def test_unknown_code_logs_code(caplog):
    client.get("/doesnotexist", follow_redirects=False)

    assert "doesnotexist" in caplog.text


def test_unknown_code_log_cannot_forge_lines(caplog):
    forged = "/abc%0AINFO:app.main:short%20link%20created%20code=FAKE1234"
    client.get(forged, follow_redirects=False)

    messages = [r.getMessage() for r in caplog.records if r.name == "app.main"]
    assert len(messages) == 1
    assert "\n" not in messages[0]


def _clicks(code):
    response = client.get(f"/links/{code}/clicks")
    assert response.status_code == 200
    return response.json()


def _follow(code, times=1):
    for _ in range(times):
        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == 302


def test_new_link_has_zero_clicks():
    code = _create("https://example.com/")

    response = client.get(f"/links/{code}/clicks")

    assert response.status_code == 200
    assert response.json() == {"code": code, "clicks": 0}


def test_each_follow_adds_one_click():
    code = _create("https://example.com/")

    _follow(code, 3)

    assert _clicks(code)["clicks"] == 3


def test_clicks_counted_per_link():
    first = _create("https://example.com/a")
    second = _create("https://example.com/b")

    _follow(first, 2)

    assert _clicks(first)["clicks"] == 2
    assert _clicks(second)["clicks"] == 0


def test_clicks_of_unknown_code_returns_404():
    response = client.get("/links/doesnotexist/clicks")

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}


def test_clicks_of_unknown_code_logs_warning(caplog):
    client.get("/links/doesnotexist/clicks")

    warnings = [r for r in caplog.records if r.name == "app.main" and r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "doesnotexist" in warnings[0].getMessage()


def test_reading_clicks_does_not_add_clicks():
    code = _create("https://example.com/")
    _follow(code, 2)

    for _ in range(3):
        assert _clicks(code)["clicks"] == 2


def test_unknown_code_follow_does_not_change_count():
    code = _create("https://example.com/")
    _follow(code)

    response = client.get("/doesnotexist", follow_redirects=False)

    assert response.status_code == 404
    assert _clicks(code)["clicks"] == 1


def test_clicks_store_and_log_no_visitor_data(caplog):
    caplog.set_level("INFO")
    code = _create("https://example.com/")

    response = client.get(
        f"/{code}",
        headers={"User-Agent": "ac7-agent", "X-Forwarded-For": "203.0.113.7"},
        follow_redirects=False,
    )
    body = _clicks(code)

    assert response.status_code == 302
    assert set(body) == {"code", "clicks"}
    assert "ac7-agent" not in caplog.text
    assert "203.0.113.7" not in caplog.text


def test_head_does_not_count():
    code = _create("https://example.com/")

    response = client.head(f"/{code}", follow_redirects=False)

    assert response.status_code != 302
    assert _clicks(code)["clicks"] == 0


def test_post_and_follow_responses_keep_their_shape():
    url = "https://example.com/shape"
    code = _create(url)
    _clicks(code)

    created = client.post("/links", json={"url": url})
    followed = client.get(f"/{code}", follow_redirects=False)

    assert created.status_code == 201
    assert set(created.json()) == {"code", "short_url"}
    assert followed.status_code == 302
    assert followed.headers["location"] == url


def test_parallel_follows_lose_no_click():
    code = _create("https://example.com/")

    def follow(_):
        return client.get(f"/{code}", follow_redirects=False).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(follow, range(50)))

    assert statuses == [302] * 50
    assert _clicks(code)["clicks"] == 50


def test_clicks_log_cannot_forge_lines(caplog):
    response = client.get("/links/abc%0AINFO:app.main:x/clicks")

    assert response.status_code == 404
    messages = [r.getMessage() for r in caplog.records if r.name == "app.main"]
    assert len(messages) == 1
    assert "\n" not in messages[0]


def test_docs_still_served():
    response = client.get("/docs")

    assert response.status_code == 200


def test_invalid_request_logged_without_url(caplog):
    response = client.post("/links", json={"url": " https://example.com/?token=secret-value"})

    assert response.status_code == 422
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "/links" in warnings[0].getMessage()
    assert "secret-value" not in caplog.text


def test_invalid_request_body_unchanged():
    response = client.post("/links", json={"url": "ftp://example.com"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"] == ["body", "url"]


def _code(prefix="My-Docs"):
    # Tests share one in-memory app: a random suffix keeps chosen codes free.
    return f"{prefix}-{secrets.token_hex(4)}"


def _create_with_code(url, code):
    response = client.post("/links", json={"url": url, "code": code})
    assert response.status_code == 201
    assert response.json()["code"] == code
    return code


def test_create_link_with_chosen_code():
    response = client.post("/links", json={"url": "https://example.com/docs", "code": "My-Docs"})

    assert response.status_code == 201
    assert response.json() == {"code": "My-Docs", "short_url": "http://testserver/My-Docs"}


def test_chosen_code_redirects_and_counts():
    url = "https://example.com/docs"
    code = _create_with_code(url, _code())

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == url
    assert _clicks(code)["clicks"] == 1


def test_taken_code_returns_409():
    code = _create_with_code("https://example.com/a", _code())

    response = client.post("/links", json={"url": "https://example.com/b", "code": code})

    assert response.status_code == 409
    assert response.json() == {"detail": "Short code already taken"}
    assert _clicks(code)["clicks"] == 0
    followed = client.get(f"/{code}", follow_redirects=False)
    assert followed.status_code == 302
    assert followed.headers["location"] == "https://example.com/a"


def test_taken_code_logs_code_not_url(caplog):
    code = _create_with_code("https://example.com/a", _code())
    caplog.set_level("INFO")

    response = client.post(
        "/links", json={"url": "https://example.com/?token=secret-value", "code": code}
    )

    assert response.status_code == 409
    warnings = [r for r in caplog.records if r.name == "app.main" and r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert code in warnings[0].getMessage()
    assert "secret-value" not in caplog.text


def test_code_differing_in_case_is_a_new_link():
    code = _code()
    _create_with_code("https://example.com/a", code)

    response = client.post("/links", json={"url": "https://example.com/b", "code": code.lower()})

    assert response.status_code == 201
    assert response.json()["code"] == code.lower()
    for each, url in ((code, "https://example.com/a"), (code.lower(), "https://example.com/b")):
        followed = client.get(f"/{each}", follow_redirects=False)
        assert followed.status_code == 302
        assert followed.headers["location"] == url


def test_random_code_cannot_be_chosen():
    code = _create("https://example.com/a")

    response = client.post("/links", json={"url": "https://example.com/b", "code": code})

    assert response.status_code == 409
    followed = client.get(f"/{code}", follow_redirects=False)
    assert followed.status_code == 302
    assert followed.headers["location"] == "https://example.com/a"


@pytest.mark.parametrize("length, status", [(2, 422), (3, 201), (32, 201), (33, 422)])
def test_chosen_code_length_limits(length, status):
    code = secrets.token_hex(17)[:length]

    response = client.post("/links", json={"url": "https://example.com/", "code": code})

    assert response.status_code == status


@pytest.mark.parametrize(
    "code", ["ab c12", "abc.12", "abc/12", "abcé12", " abc12", "abc12 ", "abc12\n"]
)
def test_chosen_code_rejects_bad_characters(code):
    before = len(links)

    response = client.post("/links", json={"url": "https://example.com/", "code": code})

    assert response.status_code == 422
    body = response.json()
    assert "code" not in body
    assert "short_url" not in body
    assert len(links) == before


@pytest.mark.parametrize("code", ["", 123])
def test_chosen_code_empty_or_not_string(code):
    response = client.post("/links", json={"url": "https://example.com/", "code": code})

    assert response.status_code == 422


def test_chosen_code_null_gives_random_code():
    response = client.post("/links", json={"url": "https://example.com/", "code": None})

    assert response.status_code == 201
    assert re.fullmatch(r"[A-Za-z0-9]{7}", response.json()["code"])


def test_bad_url_with_valid_code_keeps_code_free():
    code = _code()

    bad = client.post("/links", json={"url": "ftp://example.com", "code": code})

    assert bad.status_code == 422
    _create_with_code("https://example.com/", code)


def test_bad_url_and_bad_code_give_one_422():
    response = client.post("/links", json={"url": "ftp://example.com", "code": "a b"})

    assert response.status_code == 422
    locs = [error["loc"] for error in response.json()["detail"]]
    assert ["body", "url"] in locs
    assert ["body", "code"] in locs


def test_chosen_code_starts_with_zero_clicks():
    code = _create_with_code("https://example.com/", _code())

    assert _clicks(code) == {"code": code, "clicks": 0}


@pytest.mark.parametrize(
    "code", ["links", "health", "docs", "redoc", "Health", "DOCS", "Links", "REDOC"]
)
def test_chosen_code_rejects_reserved_names(code):
    response = client.post("/links", json={"url": "https://example.com/", "code": code})

    assert response.status_code == 422
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("prefix", ["docs", "my-health"])
def test_chosen_code_may_contain_reserved_name(prefix):
    _create_with_code("https://example.com/", _code(prefix))


def test_chosen_code_other_case_is_404():
    code = _create_with_code("https://example.com/", _code())

    followed = client.get(f"/{code.lower()}", follow_redirects=False)
    read = client.get(f"/links/{code.lower()}/clicks")

    assert followed.status_code == 404
    assert followed.json() == {"detail": "Short link not found"}
    assert read.status_code == 404
    assert read.json() == {"detail": "Short link not found"}
    assert _clicks(code)["clicks"] == 0


def test_random_code_skips_chosen_code(monkeypatch):
    chosen = _create_with_code("https://example.com/a", "Ab1" + secrets.token_hex(2))
    # The first random code drawn is the chosen one; the draws after it are real.
    chars = iter(chosen)
    real_choice = secrets.choice
    monkeypatch.setattr(
        "app.main.secrets.choice", lambda alphabet: next(chars, None) or real_choice(alphabet)
    )

    code = _create("https://example.com/b")

    assert code != chosen
    assert next(chars, None) is None


def test_random_code_works_only_in_exact_case():
    response = client.post("/links", json={"url": "https://example.com/"})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"code", "short_url"}
    code = body["code"]
    assert re.fullmatch(r"[A-Za-z0-9]{7}", code)
    if code.swapcase() != code:
        assert client.get(f"/{code.swapcase()}", follow_redirects=False).status_code == 404


def test_parallel_creates_of_one_code_give_one_201():
    code = _code()

    def create(_):
        return client.post("/links", json={"url": "https://example.com/", "code": code})

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = sorted(response.status_code for response in pool.map(create, range(20)))

    assert statuses == [201] + [409] * 19
