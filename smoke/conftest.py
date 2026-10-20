import os

import httpx
import pytest


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8080")
    with httpx.Client(base_url=base_url, timeout=10) as client:
        yield client
