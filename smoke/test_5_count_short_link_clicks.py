# Safe test data (spec A-4): links to example.com, kept in memory only.
URL = "https://example.com/"


def _create(client, url=URL):
    response = client.post("/links", json={"url": url})
    assert response.status_code == 201
    return response.json()["code"]


def _follow(client, code, times=1):
    for _ in range(times):
        response = client.get(f"/{code}")
        assert response.status_code == 302


def _clicks(client, code):
    response = client.get(f"/links/{code}/clicks")
    assert response.status_code == 200
    return response.json()


def test_ac_1_new_link_zero_clicks(client):
    code = _create(client)

    assert _clicks(client, code) == {"code": code, "clicks": 0}


def test_ac_2_three_follows_three_clicks(client):
    code = _create(client)

    _follow(client, code, 3)

    assert _clicks(client, code)["clicks"] == 3


def test_ac_3_counts_per_link(client):
    first = _create(client)
    second = _create(client)

    _follow(client, first, 2)

    assert _clicks(client, first)["clicks"] == 2
    assert _clicks(client, second)["clicks"] == 0


def test_ac_4_unknown_code_no_count(client):
    code = _create(client)
    _follow(client, code)

    response = client.get("/doesnotexist")

    assert response.status_code == 404
    assert _clicks(client, code)["clicks"] == 1


def test_ac_5_unknown_code_404(client):
    response = client.get("/links/doesnotexist/clicks")

    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}


def test_ac_6_read_does_not_count(client):
    code = _create(client)
    _follow(client, code, 2)

    for _ in range(3):
        assert _clicks(client, code)["clicks"] == 2


def test_ac_7_body_has_only_code_and_clicks(client):
    # Body keys only: smoke cannot read the app's log lines.
    code = _create(client)
    response = client.get(
        f"/{code}", headers={"User-Agent": "ac7-agent", "X-Forwarded-For": "203.0.113.7"}
    )
    assert response.status_code == 302

    assert set(_clicks(client, code)) == {"code", "clicks"}


def test_ac_8_head_no_count(client):
    code = _create(client)

    response = client.head(f"/{code}")

    assert response.status_code != 302
    assert _clicks(client, code)["clicks"] == 0


def test_ac_10_post_and_follow_same_shape(client):
    code = _create(client)
    _clicks(client, code)

    created = client.post("/links", json={"url": URL})
    followed = client.get(f"/{code}")

    assert created.status_code == 201
    assert set(created.json()) == {"code", "short_url"}
    assert followed.status_code == 302
    assert followed.headers["location"] == URL
