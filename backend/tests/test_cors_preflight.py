import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize(
    "path,method",
    [
        ("/health", "GET"),
        ("/api/health", "GET"),
        ("/upload", "POST"),
        ("/upload/", "POST"),
        ("/api/upload", "POST"),
        ("/api/upload/", "POST"),
        ("/upload/text", "POST"),
        ("/api/upload/text/", "POST"),
    ],
)
def test_preflight_options_response(client, path, method):
    origin = "https://note-bot-genai.vercel.app"
    response = client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == origin
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")
    assert method in allowed_methods
    assert "OPTIONS" in allowed_methods

    allowed_headers = response.headers.get("Access-Control-Allow-Headers", "")
    assert "Content-Type" in allowed_headers
    assert "Authorization" in allowed_headers


def test_health_endpoints(client):
    origin = "https://note-bot-genai.vercel.app"
    for path in ["/health", "/api/health"]:
        response = client.get(path, headers={"Origin": origin})
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") == "ok"
        assert response.headers.get("Access-Control-Allow-Origin") == origin
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"


def test_upload_endpoints_cors_on_error(client):
    origin = "https://note-bot-genai.vercel.app"
    for path in ["/upload", "/upload/", "/api/upload", "/api/upload/"]:
        # Unauthenticated POST should return 401, but still carry CORS headers
        response = client.post(path, headers={"Origin": origin})
        assert response.status_code == 401
        assert response.headers.get("Access-Control-Allow-Origin") == origin
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"
