import json
import sqlite3
from datetime import datetime, timezone

from . import config


def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            paypal_id TEXT,
            client_name TEXT NOT NULL,
            client_email TEXT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            pay_link TEXT,
            reminders INTEGER NOT NULL DEFAULT 0,
            agreed_plan TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            role TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_invoice(inv):
    conn = _conn()
    conn.execute(
        "INSERT INTO invoices (id, paypal_id, client_name, client_email, description, amount, currency, due_date, status, pay_link, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (inv["id"], inv.get("paypal_id"), inv["client_name"], inv.get("client_email"),
         inv["description"], inv["amount"], inv.get("currency", "USD"), inv.get("due_date"),
         inv.get("status", "DRAFT"), inv.get("pay_link"), _now()),
    )
    conn.commit()
    conn.close()
    return get_invoice(inv["id"])


def get_invoice(inv_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_invoices():
    conn = _conn()
    rows = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_invoice(inv_id, **fields):
    if not fields:
        return get_invoice(inv_id)
    keys = ", ".join(f"{k}=?" for k in fields)
    conn = _conn()
    conn.execute(f"UPDATE invoices SET {keys} WHERE id=?", (*fields.values(), inv_id))
    conn.commit()
    conn.close()
    return get_invoice(inv_id)


def add_message(invoice_id, role, body):
    conn = _conn()
    conn.execute(
        "INSERT INTO messages (invoice_id, role, body, created_at) VALUES (?,?,?,?)",
        (invoice_id, role, body, _now()),
    )
    conn.commit()
    conn.close()


def list_messages(invoice_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE invoice_id=? ORDER BY id ASC", (invoice_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
