# health-check вместо ручных curl
import pytest


@pytest.mark.integration
def test_health_ok(api_client):
    """Сервис отвечает на /api/v1/health."""
    data = api_client.get("/api/v1/health")

    # api_client.get уже кинет исключение, если не 2xx.
    # Здесь просто проверяем, что это что-то осмысленное.
    assert isinstance(data, dict)
    assert data  # не пустой JSON
