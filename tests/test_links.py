import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

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


def test_unknown_code_returns_404():
    response = client.get("/doesnotexist", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}
    assert "location" not in response.headers


def test_unknown_code_logs_code(caplog):
    client.get("/doesnotexist", follow_redirects=False)

    assert "doesnotexist" in caplog.text


def test_docs_still_served():
    response = client.get("/docs")

    assert response.status_code == 200
