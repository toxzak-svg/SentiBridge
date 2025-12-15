"""Billing service stub for managing customers, subscriptions and usage.

This file provides a minimal `BillingService` class used by route handlers and
background jobs. It should be extended to integrate with Stripe, persistent DB,
and reconciliation logic.
"""
from __future__ import annotations

from typing import Optional


class BillingService:
    """Minimal billing service stub.

    Methods here should be implemented to interact with Stripe or another
    billing provider and a durable database to store customers/subscriptions.
    """

    def __init__(self):
        # In-memory placeholder — replace with DB/Stripe client
        self._customers: dict[str, dict] = {}

    async def ensure_customer_for_user(self, user_id: str) -> str:
        """Ensure a billing customer exists for the given user.

        Returns a customer_id string.
        """
        if user_id in self._customers:
            return self._customers[user_id]["customer_id"]

        customer_id = f"cust_{user_id}"
        self._customers[user_id] = {"customer_id": customer_id, "plan": None, "active": True}
        return customer_id

    async def get_subscription_status(self, api_key_hash: str) -> dict:
        """Return a dict describing subscription status for an API key.

        Currently returns a permissive active subscription. Replace with
        real lookup against DB/Stripe.
        """
        # TODO: map api_key_hash -> customer -> subscription
        return {"active": True, "plan": "pro", "billing_model": "monthly"}

    async def record_usage(self, api_key_hash: str, endpoint: str, count: int = 1) -> None:
        """Record usage for billing purposes (stub).

        Replace with enqueue to a persistent store or direct DB write.
        """
        # No-op in stub
        return


# Singleton instance for simple import/use
billing_service = BillingService()
