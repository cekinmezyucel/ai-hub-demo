import pytest

UNSAFE_URL = 'https://example.com/a|b?q={x}&r="y"'
NON_ASCII_URL = "https://example.com/café"
SAFE_URL = "https://example.com/p%20q/r?s=1&t=a:b@c#frag"


def _create(client, url):
    response = client.post("/links", json={"url": url})
    assert response.status_code == 201
    return response.json()["code"]


def test_ac_1_unsafe_chars_encoded(client):
    code = _create(client, UNSAFE_URL)

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/a%7Cb?q=%7Bx%7D&r=%22y%22"


def test_ac_2_non_ascii_encoded(client):
    code = _create(client, NON_ASCII_URL)

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/caf%C3%A9"


def test_ac_3_safe_url_unchanged(client):
    code = _create(client, SAFE_URL)

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == SAFE_URL


@pytest.mark.parametrize(
    "url, status",
    [
        (UNSAFE_URL, 201),
        (NON_ASCII_URL, 201),
        (SAFE_URL, 201),
        ("javascript:alert(1)", 422),
    ],
)
def test_ac_6_same_urls_accepted(client, url, status):
    response = client.post("/links", json={"url": url})

    assert response.status_code == status
