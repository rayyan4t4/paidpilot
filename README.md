# PaidPilot — Get Paid, On Autopilot

**Live demo:** https://paidpilot-peach.vercel.app — dashboard, and each invoice has a client payment page at `/pay/<invoice-id>` where you can talk to the agent and watch it negotiate.
**API:** https://paidpilot-api.onrender.com (health check at `/health`)

> The live demo currently runs in demo mode: the full agent loop (invoice → follow-up → negotiation → payment confirmation) is real, while PayPal calls are simulated until sandbox credentials are provisioned. The PayPal integration code (Invoicing API + webhooks) is in `backend/app/paypal.py` and activates automatically when `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` are set.

PaidPilot is an AI agent that handles the worst part of freelancing: getting paid. A freelancer describes the job in one sentence; PaidPilot creates and sends a real PayPal invoice, watches its status through PayPal webhooks, follows up with escalating reminders when payment is late, negotiates payment plans with the client inside clear guardrails set by the freelancer, and confirms the moment money lands.

## The problem

Freelancers and small agencies lose hours every week chasing late invoices, and many simply write off money they earned. Existing invoicing tools send the first invoice and stop. PaidPilot owns the whole loop — invoice, chase, negotiate, settle — so the freelancer never has to write an awkward "just following up" email again.

## How it works

1. **One sentence in** — "Website redesign for Sara Malik, $1,200, due in 10 days." The agent parses it into a structured invoice (client, work, amount, due date) and creates it on PayPal via the Invoicing API, then sends it.
2. **The agent follows up** — when an invoice is unpaid, the agent writes and sends reminders whose tone escalates (friendly → clear → firm) based on how many reminders have already gone out.
3. **The agent negotiates** — if the client asks to split the payment or for a discount, the agent responds within a policy the freelancer controls: splits allowed only with at least 50% up front, discounts capped at 10% and only against fast settlement of the rest. It can never agree to terms outside that policy.
4. **PayPal confirms the money** — a webhook listener receives PayPal invoice events; when an invoice is paid, the dashboard updates instantly and the thread records the confirmation.
5. **One dashboard** — an AG Grid finance view shows every invoice, what's outstanding, what's overdue, reminder counts and agreed plans.

## Tech

- **PayPal Developer Platform** — Invoicing API (create/send invoices, partial payments enabled), Webhooks (payment confirmation), REST OAuth. Runs against the PayPal sandbox.
- **AI** — an LLM (via OpenRouter) does three jobs: parsing free-text job descriptions into invoices, writing context-aware reminder emails at three escalation levels, and negotiating with clients under hard policy guardrails. Every AI path has a deterministic fallback, so the product never breaks if the model is unavailable.
- **Backend** — FastAPI (Python), SQLite store, async httpx PayPal client.
- **Frontend** — React + TypeScript + Vite, AG Grid for the finance dashboard.

## Run it

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your PayPal sandbox Client ID + Secret, and an OpenRouter key
uvicorn app.main:app --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, type a sentence like "Logo design for Ahmed Raza, $450, due in 7 days", and watch the agent work. Without PayPal credentials the backend runs in demo mode (simulated invoices and payments) so the full flow can be explored; add sandbox credentials to `.env` and the same code talks to the real PayPal sandbox.

To receive payment webhooks locally, expose the backend (e.g. `ngrok http 8000`) and register the tunnel URL + `/webhooks/paypal` in your PayPal app's webhook settings.

## License

MIT — see [LICENSE](LICENSE).
