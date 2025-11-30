import pytest


@pytest.mark.integration
def test_health_ok(api_client):
    data = api_client.get("/api/v1/health")
    assert isinstance(data, dict)
    assert data  # не пустой JSON
