import pytest
from fastapi.testclient import TestClient

from query_gateway import api

client = TestClient(api.app)


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # The routes read DEMO_SLEEP_SECONDS at call time, so this keeps tests fast.
    monkeypatch.setattr(api, "DEMO_SLEEP_SECONDS", 0)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("path", "name"),
    [("/demo/blocking", "blocking"), ("/demo/to-thread", "to-thread")],
)
def test_demo_endpoints_respond(no_sleep: None, path: str, name: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {"endpoint": name}
