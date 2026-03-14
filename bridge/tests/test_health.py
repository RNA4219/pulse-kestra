"""Test health endpoint."""

from fastapi.testclient import TestClient

from bridge.main import create_app


def test_health_returns_ok():
    """Test that /health returns 200 OK regardless of configuration."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_works_without_settings():
    """Test that /health works even with incomplete settings."""
    # Create app without any settings configured
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    # Should still return 200 - this is a liveness check
    assert response.status_code == 200