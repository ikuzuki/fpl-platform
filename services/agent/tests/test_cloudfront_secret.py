"""Unit tests for the CloudFront shared-secret middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fpl_agent.middleware.cloudfront_secret import CloudFrontSecretMiddleware

pytestmark = pytest.mark.unit


def _build_app(*, header_name: str = "X-CloudFront-Secret", secret_value: str) -> FastAPI:
    """Tiny FastAPI app with the middleware attached and three routes:

    * ``/health`` — exempt, must always answer 200 regardless of header
    * ``/team`` — protected, models the agent's squad endpoint
    * ``/chat`` — protected, models the agent's SSE endpoint
    """
    app = FastAPI()
    app.add_middleware(
        CloudFrontSecretMiddleware, header_name=header_name, secret_value=secret_value
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/team")
    def team() -> dict[str, str]:
        return {"picks": "15"}

    @app.post("/chat")
    def chat() -> dict[str, str]:
        return {"reply": "ok"}

    return app


class TestRejectsMissingHeader:
    def test_get_without_header_returns_401(self) -> None:
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).get("/team")
        assert res.status_code == 401
        assert res.json() == {"detail": "unauthorized"}

    def test_post_without_header_returns_401(self) -> None:
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).post("/chat", json={"question": "q"})
        assert res.status_code == 401

    def test_wrong_header_value_returns_401(self) -> None:
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).get("/team", headers={"X-CloudFront-Secret": "wrong"})
        assert res.status_code == 401


class TestAcceptsCorrectHeader:
    def test_get_with_header_passes_through(self) -> None:
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).get("/team", headers={"X-CloudFront-Secret": "s3cret"})
        assert res.status_code == 200
        assert res.json() == {"picks": "15"}

    def test_post_with_header_passes_through(self) -> None:
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).post(
            "/chat", json={"question": "q"}, headers={"X-CloudFront-Secret": "s3cret"}
        )
        assert res.status_code == 200


class TestHealthExemption:
    def test_health_always_passes_even_without_header(self) -> None:
        """LWA's in-container readiness probe hits /health before CloudFront routing.

        Without the exemption the probe would block forever because the secret
        isn't in scope inside the Lambda sandbox itself.
        """
        app = _build_app(secret_value="s3cret")
        res = TestClient(app).get("/health")
        assert res.status_code == 200


class TestDisabledWhenSecretEmpty:
    def test_empty_secret_treats_middleware_as_no_op(self) -> None:
        """Local dev + unit tests run without a secret — middleware must no-op."""
        app = _build_app(secret_value="")
        res = TestClient(app).get("/team")  # no header at all
        assert res.status_code == 200


class TestConfigurableHeaderName:
    def test_custom_header_name_is_honoured(self) -> None:
        app = _build_app(header_name="X-My-Custom", secret_value="s3cret")
        res = TestClient(app).get("/team", headers={"X-My-Custom": "s3cret"})
        assert res.status_code == 200
