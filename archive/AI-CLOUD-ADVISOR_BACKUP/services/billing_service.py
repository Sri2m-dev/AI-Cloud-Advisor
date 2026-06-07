import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from database.db import get_company_subscription, get_plan_definition, update_company_plan, upsert_company_subscription

try:
    import stripe
except ImportError:
    stripe = None


def _to_iso8601(timestamp):
    if not timestamp:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat(timespec="seconds")


def get_billing_app_url():
    return os.getenv("CLOUD_ADVISOR_APP_URL", "").rstrip("/")


def get_billing_configuration_status():
    return {
        "stripe_available": stripe is not None,
        "stripe_secret_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
        "app_url_configured": bool(get_billing_app_url()),
    }


def billing_is_ready():
    config = get_billing_configuration_status()
    return all(config.values())


def _stripe_client():
    if stripe is None:
        raise RuntimeError("Stripe SDK is not installed. Add the stripe package to enable billing.")
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    if not get_billing_app_url():
        raise RuntimeError("CLOUD_ADVISOR_APP_URL is not configured.")
    stripe.api_key = secret_key
    return stripe


def _build_return_url(params=None):
    base_url = get_billing_app_url()
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def create_checkout_session(company_name, username, plan_name, billing_cycle="monthly"):
    stripe_client = _stripe_client()
    normalized_cycle = "yearly" if str(billing_cycle).lower() == "yearly" else "monthly"
    interval = "year" if normalized_cycle == "yearly" else "month"
    plan_def = get_plan_definition(plan_name)
    amount = plan_def["yearly_price"] if normalized_cycle == "yearly" else plan_def["monthly_price"]
    trial_days = int(plan_def.get("trial_days") or 0)
    metadata = {
        "company_name": company_name,
        "username": username,
        "plan_name": plan_name,
        "billing_cycle": normalized_cycle,
    }
    session = stripe_client.checkout.Session.create(
        mode="subscription",
        success_url=_build_return_url({"billing_result": "success", "session_id": "{CHECKOUT_SESSION_ID}"}),
        cancel_url=_build_return_url({"billing_result": "cancel"}),
        client_reference_id=company_name,
        payment_method_collection="always",
        allow_promotion_codes=True,
        metadata=metadata,
        subscription_data={
            "trial_period_days": trial_days,
            "metadata": metadata,
        },
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(amount * 100),
                    "product_data": {
                        "name": f"Cloud Advisor {plan_name}",
                        "description": f"{trial_days}-day free trial, then ${amount} per {interval}.",
                    },
                    "recurring": {"interval": interval},
                },
                "quantity": 1,
            }
        ],
    )
    upsert_company_subscription(
        company_name,
        plan_name=plan_name,
        billing_cycle=normalized_cycle,
        subscription_status="checkout_started",
        stripe_checkout_session_id=session.id,
        source="stripe",
        last_synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return {"id": session.id, "url": session.url}


def sync_checkout_session(company_name, session_id):
    stripe_client = _stripe_client()
    session = stripe_client.checkout.Session.retrieve(session_id, expand=["subscription", "customer"])
    if not session:
        raise RuntimeError("Stripe checkout session could not be found.")

    metadata = dict(getattr(session, "metadata", {}) or {})
    subscription = getattr(session, "subscription", None)
    customer = getattr(session, "customer", None)
    if not subscription:
        raise RuntimeError("Stripe checkout session completed without a subscription object.")

    plan_name = metadata.get("plan_name") or get_company_subscription(company_name).get("plan") or "Starter"
    billing_cycle = metadata.get("billing_cycle") or get_company_subscription(company_name).get("billing_cycle") or "monthly"
    current_period_end = _to_iso8601(getattr(subscription, "current_period_end", None))
    trial_started_at = _to_iso8601(getattr(subscription, "trial_start", None))
    trial_ends_at = _to_iso8601(getattr(subscription, "trial_end", None))
    items = getattr(getattr(subscription, "items", None), "data", []) or []
    price_id = None
    if items and getattr(items[0], "price", None):
        price_id = getattr(items[0].price, "id", None)

    update_company_plan(company_name, plan_name)
    return upsert_company_subscription(
        company_name,
        plan_name=plan_name,
        billing_cycle=billing_cycle,
        subscription_status=getattr(subscription, "status", "active"),
        trial_started_at=trial_started_at,
        trial_ends_at=trial_ends_at,
        cancel_at_period_end=bool(getattr(subscription, "cancel_at_period_end", False)),
        stripe_customer_id=getattr(customer, "id", customer if isinstance(customer, str) else None),
        stripe_subscription_id=getattr(subscription, "id", None),
        stripe_checkout_session_id=session.id,
        stripe_price_id=price_id,
        current_period_end=current_period_end,
        source="stripe",
        last_synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def sync_company_subscription(company_name):
    stripe_client = _stripe_client()
    subscription_row = get_company_subscription(company_name)
    if not subscription_row or not subscription_row.get("stripe_subscription_id"):
        return subscription_row

    subscription = stripe_client.Subscription.retrieve(subscription_row["stripe_subscription_id"])
    items = getattr(getattr(subscription, "items", None), "data", []) or []
    price_id = None
    if items and getattr(items[0], "price", None):
        price_id = getattr(items[0].price, "id", None)

    return upsert_company_subscription(
        company_name,
        plan_name=subscription_row.get("plan") or "Starter",
        billing_cycle=subscription_row.get("billing_cycle") or "monthly",
        subscription_status=getattr(subscription, "status", subscription_row.get("subscription_status") or "inactive"),
        trial_started_at=_to_iso8601(getattr(subscription, "trial_start", None)),
        trial_ends_at=_to_iso8601(getattr(subscription, "trial_end", None)),
        cancel_at_period_end=bool(getattr(subscription, "cancel_at_period_end", False)),
        stripe_customer_id=subscription_row.get("stripe_customer_id"),
        stripe_subscription_id=getattr(subscription, "id", subscription_row.get("stripe_subscription_id")),
        stripe_checkout_session_id=subscription_row.get("stripe_checkout_session_id"),
        stripe_price_id=price_id,
        current_period_end=_to_iso8601(getattr(subscription, "current_period_end", None)),
        source="stripe",
        last_synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def create_billing_portal_session(company_name):
    stripe_client = _stripe_client()
    subscription_row = get_company_subscription(company_name)
    customer_id = subscription_row.get("stripe_customer_id") if subscription_row else None
    if not customer_id:
        raise RuntimeError("No Stripe customer is linked to this company yet.")
    session = stripe_client.billing_portal.Session.create(
        customer=customer_id,
        return_url=_build_return_url({"selected_page": "Plans & Billing"}),
    )
    return {"id": session.id, "url": session.url}

