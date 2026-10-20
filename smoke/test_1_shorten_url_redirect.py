import pytest

URL = "https://example.com/some/long/path?x=1"


def test_ac_1_create_link(client):
    response = client.post("/links", json={"url": URL})

    assert response.status_code == 201
    body = response.json()
    assert body["code"]
    assert body["short_url"].endswith("/" + body["code"])


@pytest.mark.parametrize(
    "body",
    [
        {"url": "javascript:alert(1)"},
        {"url": "ftp://example.com"},
        {"url": "/relative/path"},
        {"url": "https://"},
        {"url": ""},
        {},
    ],
)
def test_ac_3_invalid_url_rejected(client, body):
    response = client.post("/links", json=body)

    assert response.status_code == 422
    assert "detail" in response.json()
    assert "code" not in response.json()
    assert "short_url" not in response.json()


def test_ac_4_url_length_limit(client):
    prefix = "https://example.com/"

    ok = client.post("/links", json={"url": prefix + "a" * (2048 - len(prefix))})
    too_long = client.post("/links", json={"url": prefix + "a" * (2049 - len(prefix))})

    assert ok.status_code == 201
    assert too_long.status_code == 422
    assert "detail" in too_long.json()
