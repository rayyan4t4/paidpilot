import json
import re
from datetime import date, timedelta

import httpx

from . import config

DEFAULT_POLICY = {"allow_split": True, "max_discount_pct": 10, "min_first_pct": 50}


async def _llm(system, user):
    if not config.OPENROUTER_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def _fallback_parse(text):
    amount = None
    m = re.search(r"\$\s?([\d,]+(?:\.\d{1,2})?)", text)
    if m:
        amount = float(m.group(1).replace(",", ""))
    due = date.today() + timedelta(days=7)
    m = re.search(r"due in (\d+) days", text, re.I)
    if m:
        due = date.today() + timedelta(days=int(m.group(1)))
    name = "Client"
    m = re.search(r"for ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)", text)
    if m:
        name = m.group(1)
    desc = re.sub(r",?\s*due in \d+ days\.?", "", text, flags=re.I).strip().rstrip(".")
    return {"client_name": name, "client_email": None, "description": desc or text,
            "amount": amount or 0, "currency": "USD", "due_date": due.isoformat()}


async def parse_invoice_text(text):
    out = await _llm(
        "Extract invoice fields from the user's sentence. Reply with ONLY a JSON object: "
        '{"client_name": str, "client_email": str|null, "description": str, "amount": number, '
        '"currency": "USD", "due_in_days": int}. Default due_in_days 7.',
        text,
    )
    if out:
        try:
            data = json.loads(out[out.index("{"):out.rindex("}") + 1])
            due = date.today() + timedelta(days=int(data.get("due_in_days", 7)))
            return {"client_name": data["client_name"], "client_email": data.get("client_email"),
                    "description": data["description"], "amount": float(data["amount"]),
                    "currency": data.get("currency", "USD"), "due_date": due.isoformat()}
        except Exception:
            pass
    return _fallback_parse(text)


async def write_reminder(inv, level):
    tones = {1: "friendly and light", 2: "polite but clear that payment is overdue", 3: "firm and final-notice tone, professional"}
    out = await _llm(
        "You are PaidPilot, an assistant that collects payments for a freelancer. Write a short payment reminder email (3-5 sentences, no subject line). "
        f"Tone: {tones.get(level, tones[3])}. Mention the work, amount, and that the PayPal invoice link is the easy way to pay. Never threaten.",
        f"Client: {inv['client_name']}. Work: {inv['description']}. Amount: {inv['currency']} {inv['amount']:.2f}. Due date: {inv['due_date']}. Reminders already sent: {inv['reminders']}.",
    )
    if out:
        return out.strip()
    return (f"Hi {inv['client_name']}, a quick note that payment of {inv['currency']} {inv['amount']:.2f} "
            f"for {inv['description']} was due on {inv['due_date']}. You can pay in a minute via the PayPal invoice link. "
            f"Thanks a lot!")


async def negotiate(inv, client_msg, policy):
    policy = {**DEFAULT_POLICY, **(policy or {})}
    out = await _llm(
        "You are PaidPilot negotiating payment of an overdue invoice for a freelancer. Decide the reply AND the action. "
        f"Policy you must not break: split payments allowed = {policy['allow_split']}; the first installment must be at least {policy['min_first_pct']}% of the total; "
        f"maximum discount you may offer = {policy['max_discount_pct']}% and only if the client pays the rest within 7 days. "
        'Reply with ONLY a JSON object: {"reply": str, "action": "none"|"split"|"discount", "first_pct": number|null, "discount_pct": number|null}. '
        "Be warm, brief, and clear in the reply.",
        f"Invoice: {inv['description']} for {inv['currency']} {inv['amount']:.2f}, due {inv['due_date']}, status {inv['status']}. Client says: {client_msg}",
    )
    if out:
        try:
            data = json.loads(out[out.index("{"):out.rindex("}") + 1])
            if data.get("action") == "discount" and (data.get("discount_pct") or 0) > policy["max_discount_pct"]:
                data = {"reply": "I understand. I can't reduce the amount, but I can split it into two payments if that helps.", "action": "split" if policy["allow_split"] else "none", "first_pct": policy["min_first_pct"], "discount_pct": None}
            if data.get("action") == "split" and (data.get("first_pct") or 0) < policy["min_first_pct"]:
                data["first_pct"] = policy["min_first_pct"]
            return data
        except Exception:
            pass
    if policy["allow_split"]:
        return {"reply": f"I understand — happy to split it: {policy['min_first_pct']}% now via the PayPal invoice link and the rest within 14 days. Shall I update the invoice?", "action": "split", "first_pct": policy["min_first_pct"], "discount_pct": None}
    return {"reply": "I understand. The full amount is due, but paying via the PayPal link only takes a minute whenever you're ready.", "action": "none", "first_pct": None, "discount_pct": None}
