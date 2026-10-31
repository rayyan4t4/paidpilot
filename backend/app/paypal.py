import time
import uuid

import httpx

from . import config

_token = {"value": None, "expires_at": 0.0}


async def _access_token():
    if _token["value"] and time.time() < _token["expires_at"]:
        return _token["value"]
    async with httpx.AsyncClient(base_url=config.PAYPAL_BASE, timeout=30) as client:
        r = await client.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
        )
        r.raise_for_status()
        data = r.json()
        _token["value"] = data["access_token"]
        _token["expires_at"] = time.time() + max(60, int(data.get("expires_in", 3600)) - 120)
        return _token["value"]


async def _headers():
    return {"Authorization": f"Bearer {await _access_token()}", "Content-Type": "application/json"}


async def create_invoice(inv):
    if config.MOCK_MODE:
        pid = "MOCK-" + uuid.uuid4().hex[:12].upper()
        return {"paypal_id": pid, "pay_link": f"https://www.sandbox.paypal.com/invoice/payerView/details/{pid}", "status": "DRAFT"}
    payload = {
        "detail": {
            "invoice_number": inv["id"],
            "invoice_date": inv["created_date"],
            "payment_term": {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": inv["due_date"]},
            "currency_code": inv.get("currency", "USD"),
        },
        "invoicer_info": {"business_name": "PaidPilot User"},
        "primary_recipients": [
            {"billing_info": {"name": {"given_name": inv["client_name"]}, "email_address": inv.get("client_email") or "client@example.com"}}
        ],
        "items": [
            {"name": inv["description"], "quantity": "1", "unit_amount": {"currency_code": inv.get("currency", "USD"), "value": f"{inv['amount']:.2f}"}}
        ],
        "configuration": {"partial_payment": {"allow_partial_payment": True}},
    }
    async with httpx.AsyncClient(base_url=config.PAYPAL_BASE, timeout=30) as client:
        r = await client.post("/v2/invoicing/invoices", json=payload, headers=await _headers())
        r.raise_for_status()
        href = r.headers.get("location", "")
        pid = href.rstrip("/").split("/")[-1]
        detail = (await client.get(f"/v2/invoicing/invoices/{pid}", headers=await _headers())).json()
        link = next((l["href"] for l in detail.get("links", []) if l.get("rel") == "payer-view"), "")
        return {"paypal_id": pid, "pay_link": link, "status": detail.get("status", "DRAFT")}


async def send_invoice(paypal_id):
    if config.MOCK_MODE:
        return {"status": "SENT"}
    async with httpx.AsyncClient(base_url=config.PAYPAL_BASE, timeout=30) as client:
        r = await client.post(
            f"/v2/invoicing/invoices/{paypal_id}/send",
            json={"send_to_invoicer": True},
            headers=await _headers(),
        )
        r.raise_for_status()
        return {"status": "SENT"}


async def get_invoice(paypal_id):
    if config.MOCK_MODE:
        return None
    async with httpx.AsyncClient(base_url=config.PAYPAL_BASE, timeout=30) as client:
        r = await client.get(f"/v2/invoicing/invoices/{paypal_id}", headers=await _headers())
        r.raise_for_status()
        return r.json()
