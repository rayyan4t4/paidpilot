export interface Invoice {
  id: string
  paypal_id: string | null
  client_name: string
  client_email: string | null
  description: string
  amount: number
  currency: string
  due_date: string
  status: string
  pay_link: string | null
  reminders: number
  agreed_plan: string | null
  created_at: string
}

export interface Message {
  id: number
  role: string
  body: string
  created_at: string
}

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function req(path: string, options?: RequestInit) {
  const r = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.detail || r.statusText)
  return r.json()
}

export const api = {
  health: () => req('/health'),
  listInvoices: (): Promise<Invoice[]> => req('/api/invoices'),
  invoice: (id: string): Promise<Invoice & { messages: Message[] }> => req(`/api/invoices/${id}`),
  fromText: (text: string): Promise<Invoice> => req('/api/invoices/from-text', { method: 'POST', body: JSON.stringify({ text }) }),
  remind: (id: string) => req(`/api/invoices/${id}/remind`, { method: 'POST' }),
  clientMessage: (id: string, message: string) => req(`/api/invoices/${id}/client-message`, { method: 'POST', body: JSON.stringify({ message }) }),
  simulatePay: (id: string) => req(`/api/invoices/${id}/simulate-pay`, { method: 'POST' }),
}
