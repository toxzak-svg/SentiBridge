import json
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.main import create_app


def test_subscribe_and_portal(monkeypatch):
    app = create_app()
    client = TestClient(app)

    # Stub billing_service.ensure_customer_for_user and mount router
    from src.routers import billing as billing_mod
    app.include_router(billing_mod.router, prefix="/api/v1")

    async def fake_ensure(user_id):
        return "cust_test"

    monkeypatch.setattr(billing_mod, "billing_service", type("S", (), {"ensure_customer_for_user": fake_ensure}))

    headers = {"X-API-Key": "test"}
    resp = client.post("/api/v1/billing/subscribe", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "checkout_url" in body and "cust_test" in body["checkout_url"]

    resp = client.get("/api/v1/billing/portal", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "portal_url" in body and "cust_test" in body["portal_url"]


def test_webhook_no_secret_accepts_plain_body(monkeypatch):
    app = create_app()
    client = TestClient(app)

    from src.routers import billing as billing_mod
    app.include_router(billing_mod.router, prefix="/api/v1")

    # Ensure no webhook secret configured
    billing_mod.settings.webhook_secret = None

    headers = {"X-API-Key": "test"}
    # Send non-JSON body; handler should catch JSON parse error and return event=None
    resp = client.post("/api/v1/billing/webhook", data="not-a-json", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("received") is True
    assert body.get("event") is None


def test_webhook_with_secret_requires_header(monkeypatch):
    app = create_app()
    client = TestClient(app)

    from src.routers import billing as billing_mod
    app.include_router(billing_mod.router, prefix="/api/v1")

    billing_mod.settings.webhook_secret = SecretStr("expected_sig")

    headers = {"X-API-Key": "test"}
    # Missing signature header should produce 400
    resp = client.post("/api/v1/billing/webhook", json={"event": "x"}, headers=headers)
    assert resp.status_code == 400

    # Wrong signature
    resp = client.post("/api/v1/billing/webhook", json={"event": "x"}, headers={**headers, "Stripe-Signature": "bad"})
    assert resp.status_code == 400

    # Correct signature
    resp = client.post(
        "/api/v1/billing/webhook",
        json={"event": "x"},
        headers={**headers, "Stripe-Signature": billing_mod.settings.webhook_secret.get_secret_value()},
    )
    assert resp.status_code == 200
