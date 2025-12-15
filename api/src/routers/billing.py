"""Billing endpoints: subscription onboarding and webhook receiver.

Endpoints:
- POST /billing/subscribe : create a checkout/session URL (stub)
- GET  /billing/portal    : return a billing portal URL (stub)
- POST /billing/webhook   : Stripe webhook receiver (verifies signature if configured)

This router uses the `billing_service` stub for basic behavior. Replace
stubs with real Stripe integration and DB writes for production.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.services.billing import billing_service

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


@router.post("/subscribe")
async def subscribe(current_user=Depends(lambda: None)):
    """Create a subscription checkout link for the current user (stub).

    In production, create a Stripe Checkout Session and return the session URL.
    """
    # In real implementation, current_user should be a validated TokenData
    user_id = getattr(current_user, "sub", "anonymous") if current_user else "anonymous"
    customer_id = await billing_service.ensure_customer_for_user(user_id)

    # Return a placeholder URL — replace with Stripe Checkout URL
    return {"checkout_url": f"https://billing.example.com/checkout?customer={customer_id}"}


@router.get("/portal")
async def portal(current_user=Depends(lambda: None)):
    """Return a billing portal URL for the current user (stub)."""
    user_id = getattr(current_user, "sub", "anonymous") if current_user else "anonymous"
    customer_id = await billing_service.ensure_customer_for_user(user_id)
    return {"portal_url": f"https://billing.example.com/portal?customer={customer_id}"}


@router.post("/webhook")
async def webhook(request: Request, stripe_signature: str | None = Header(None)):
    """Receive Stripe webhook events.

    Verifies `Stripe-Signature` against configured `settings.webhook_secret` if present.
    This is a minimal implementation — handle events and update your DB/subscriptions
    accordingly in a production system.
    """
    body = await request.body()

    # If webhook secret configured, require signature header
    if settings.webhook_secret:
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
        # Minimal verification: compare provided header to webhook_secret (not Stripe's method)
        # Replace this with stripe.Webhook.construct_event(...) when using Stripe SDK
        if stripe_signature != settings.webhook_secret.get_secret_value():
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Parse event minimally
    try:
        event_json = await request.json()
    except Exception:
        event_json = None

    # TODO: handle events like `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`

    # For now, just acknowledge receipt
    return JSONResponse(status_code=200, content={"received": True, "event": event_json})
