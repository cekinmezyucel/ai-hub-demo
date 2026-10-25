import secrets

# Safe test data (spec A-4): links to example.com with suffixed codes, kept in memory only.
URL = "https://example.com/"


def _code(prefix="My-Docs"):
    # A fixed code would give 409 on the second run against the same app.
    return f"{prefix}-{secrets.token_hex(4)}"


def _post(client, code, url=URL):
    return client.post("/links", json={"url": url, "code": code})


def _create_with_code(client, code, url=URL):
    response = _post(client, code, url)
    assert response.status_code == 201
    assert response.json()["code"] == code
    return code


def _clicks(client, code):
    response = client.get(f"/links/{code}/clicks")
    assert response.status_code == 200
    return response.json()


def test_ac_1_chosen_code_created(client):
    code = _code()

    response = _post(client, code)

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == code
    assert body["short_url"].endswith(f"/{code}")


def test_ac_2_chosen_code_redirects_and_counts(client):
    code = _create_with_code(client, _code())

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == URL
    assert _clicks(client, code)["clicks"] == 1


def test_ac_4_taken_code_409(client):
    code = _create_with_code(client, _code())

    response = _post(client, code, "https://example.com/b")

    assert response.status_code == 409
    assert response.json() == {"detail": "Short code already taken"}
    followed = client.get(f"/{code}")
    assert followed.status_code == 302
    assert followed.headers["location"] == URL


def test_ac_5_other_case_is_new_link(client):
    code = _create_with_code(client, _code())

    _create_with_code(client, code.lower(), "https://example.com/b")

    assert client.get(f"/{code}").headers["location"] == URL
    assert client.get(f"/{code.lower()}").headers["location"] == "https://example.com/b"


def test_ac_6_random_code_taken_409(client):
    created = client.post("/links", json={"url": URL})
    assert created.status_code == 201
    code = created.json()["code"]

    response = _post(client, code, "https://example.com/b")

    assert response.status_code == 409
    assert client.get(f"/{code}").headers["location"] == URL


def test_ac_7_length_limits(client):
    for length, status in ((2, 422), (3, 201), (32, 201), (33, 422)):
        code = secrets.token_hex(17)[:length]
        assert _post(client, code).status_code == status, length


def test_ac_8_bad_characters_422(client):
    for code in ("ab c12", "abc.12", "abc/12", "abcé12", " abc12", "abc12 "):
        response = _post(client, code)
        assert response.status_code == 422, code
        assert "short_url" not in response.json()


def test_ac_9_reserved_names_422(client):
    for code in ("links", "health", "docs", "redoc", "Health", "DOCS"):
        assert _post(client, code).status_code == 422, code

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200


def test_ac_10_empty_null_non_string(client):
    assert _post(client, "").status_code == 422
    assert _post(client, 123).status_code == 422

    response = _post(client, None)

    assert response.status_code == 201
    assert len(response.json()["code"]) == 7


def test_ac_11_chosen_code_zero_clicks(client):
    code = _create_with_code(client, _code())

    assert _clicks(client, code) == {"code": code, "clicks": 0}
