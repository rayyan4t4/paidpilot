import uuid
from datetime import date, datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent, config, paypal, store

app = FastAPI(title="PaidPilot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class FromText(BaseModel):
    text: str


class ClientMessage(BaseModel):
    message: str
    policy: dict | None = None


store.init()


@app.get("/health")
def health():
    return {"ok": True, "mock_mode": config.MOCK_MODE}


@app.post("/api/invoices/from-text")
async def invoice_from_text(body: FromText):
    parsed = await agent.parse_invoice_text(body.text)
    if not parsed["amount"]:
        raise HTTPException(400, "Could not find an amount in that sentence. Include one, e.g. $450.")
    inv_id = "PP-" + uuid.uuid4().hex[:8].upper()
    draft = {**parsed, "id": inv_id, "created_date": date.today().isoformat()}
    pp = await paypal.create_invoice(draft)
    inv = store.create_invoice({**draft, **pp})
    await paypal.send_invoice(inv["paypal_id"])
    inv = store.update_invoice(inv_id, status="SENT")
    store.add_message(inv_id, "agent", f"Invoice created from: {body.text}")
    return inv


@app.get("/api/invoices")
def invoices():
    return store.list_invoices()


@app.get("/api/invoices/{inv_id}")
def invoice_detail(inv_id: str):
    inv = store.get_invoice(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return {**inv, "messages": store.list_messages(inv_id)}


@app.post("/api/invoices/{inv_id}/remind")
async def remind(inv_id: str):
    inv = store.get_invoice(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv["status"] == "PAID":
        raise HTTPException(400, "Invoice is already paid")
    level = min(inv["reminders"] + 1, 3)
    body = await agent.write_reminder(inv, level)
    store.add_message(inv_id, "agent", body)
    inv = store.update_invoice(inv_id, reminders=inv["reminders"] + 1)
    return {"invoice": inv, "reminder": body, "level": level}


@app.post("/api/invoices/{inv_id}/client-message")
async def client_message(inv_id: str, body: ClientMessage):
    inv = store.get_invoice(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    store.add_message(inv_id, "client", body.message)
    result = await agent.negotiate(inv, body.message, body.policy)
    store.add_message(inv_id, "agent", result["reply"])
    if result["action"] in ("split", "discount"):
        plan = {"action": result["action"], "first_pct": result.get("first_pct"), "discount_pct": result.get("discount_pct")}
        import json
        inv = store.update_invoice(inv_id, agreed_plan=json.dumps(plan))
    return {"invoice": inv, "reply": result["reply"], "action": result["action"]}


@app.post("/api/invoices/{inv_id}/simulate-pay")
def simulate_pay(inv_id: str):
    inv = store.get_invoice(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv = store.update_invoice(inv_id, status="PAID")
    store.add_message(inv_id, "system", "Payment received (simulated in demo mode).")
    return inv


@app.post("/api/demo/seed")
def demo_seed():
    if store.list_invoices():
        return {"seeded": 0, "note": "Invoices already exist"}
    from datetime import timedelta
    import json
    today = date.today()
    samples = [
        {"id": "PP-SEED01", "client_name": "Sara Malik", "client_email": "sara@example.com",
         "description": "Website redesign", "amount": 1200, "due": today + timedelta(days=3), "status": "SENT", "reminders": 0, "plan": None},
        {"id": "PP-SEED02", "client_name": "Ahmed Raza", "client_email": "ahmed@example.com",
         "description": "Logo and brand kit", "amount": 450, "due": today - timedelta(days=5), "status": "SENT", "reminders": 2, "plan": None},
        {"id": "PP-SEED03", "client_name": "Bilal Hussain", "client_email": "bilal@example.com",
         "description": "Mobile app UI kit", "amount": 800, "due": today - timedelta(days=10), "status": "PAID", "reminders": 1, "plan": None},
        {"id": "PP-SEED04", "client_name": "Fatima Noor", "client_email": "fatima@example.com",
         "description": "Social media content pack", "amount": 300, "due": today - timedelta(days=2), "status": "SENT", "reminders": 1,
         "plan": {"action": "split", "first_pct": 50, "discount_pct": None}},
    ]
    for s in samples:
        store.create_invoice({
            "id": s["id"], "paypal_id": f"MOCK-{s['id']}", "client_name": s["client_name"],
            "client_email": s["client_email"], "description": s["description"], "amount": s["amount"],
            "currency": "USD", "due_date": s["due"].isoformat(), "status": s["status"],
            "pay_link": f"https://www.sandbox.paypal.com/invoice/payerView/details/MOCK-{s['id']}",
        })
        store.update_invoice(s["id"], reminders=s["reminders"],
                             agreed_plan=json.dumps(s["plan"]) if s["plan"] else None)
    store.add_message("PP-SEED02", "agent", "Hi Ahmed Raza, a quick note that payment of USD 450.00 for Logo and brand kit was due recently. You can pay in a minute via the PayPal invoice link. Thanks a lot!")
    store.add_message("PP-SEED03", "system", "PayPal webhook: INVOICING.INVOICE.PAID — payment confirmed.")
    store.add_message("PP-SEED04", "client", "This month is tight — can I pay half now and the rest later?")
    store.add_message("PP-SEED04", "agent", "I understand — happy to split it: 50% now via the PayPal invoice link and the rest within 14 days. Shall I update the invoice?")
    return {"seeded": len(samples)}


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    event = await request.json()
    etype = event.get("event_type", "")
    resource = event.get("resource", {})
    if "INVOICE" in etype and "PAID" in etype:
        number = resource.get("detail", {}).get("invoice_number")
        if number and store.get_invoice(number):
            store.update_invoice(number, status="PAID")
            store.add_message(number, "system", f"PayPal webhook: {etype} — payment confirmed.")
    return {"received": True, "event_type": etype, "at": datetime.now(timezone.utc).isoformat()}
