import { useCallback, useEffect, useState } from 'react'
import { api, type Invoice, type Message } from './api'

export default function ClientPay({ invoiceId }: { invoiceId: string }) {
  const [inv, setInv] = useState<(Invoice & { messages: Message[] }) | null>(null)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try { setInv(await api.invoice(invoiceId)) } catch { setError('Invoice not found.') }
  }, [invoiceId])

  useEffect(() => { load() }, [load])

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!inv) return <div className="page"><p>Loading…</p></div>

  const paid = inv.status === 'PAID'

  const send = async () => {
    if (!msg.trim()) return
    await api.clientMessage(invoiceId, msg.trim())
    setMsg('')
    load()
  }

  const payNow = async () => {
    await api.simulatePay(invoiceId)
    load()
  }

  return (
    <div className="page pay-page">
      <header>
        <h1>Invoice from your freelancer</h1>
        <p>{inv.description}</p>
      </header>
      <section className="pay-card">
        <div className="pay-amount">${inv.amount.toFixed(2)}</div>
        <p>Client: {inv.client_name} · Due: {inv.due_date}</p>
        <p>Status: <strong style={{ color: paid ? '#0a6c4f' : '#7a5b00' }}>{inv.status}</strong></p>
        {inv.agreed_plan && <p className="plan">Agreed plan: {inv.agreed_plan}</p>}
        {!paid && (
          inv.pay_link && !inv.pay_link.includes('MOCK-')
            ? <a className="pay-btn" href={inv.pay_link} target="_blank" rel="noreferrer">Pay with PayPal</a>
            : <button className="pay-btn" onClick={payNow}>Pay with PayPal</button>
        )}
        {paid && <p className="paid-note">Paid — thank you! Your freelancer has been notified.</p>}
      </section>

      <section className="chat-card">
        <h3>Messages</h3>
        <div className="thread">
          {inv.messages.filter(m => m.role !== 'system').map((m, i) => (
            <div key={i} className={`msg ${m.role}`}><span>{m.role === 'agent' ? 'PaidPilot agent' : 'You'}</span>{m.body}</div>
          ))}
        </div>
        {!paid && (
          <div className="reply">
            <input value={msg} onChange={e => setMsg(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder='Ask about this invoice, e.g. "Can I pay half now?"' />
            <button onClick={send}>Send</button>
          </div>
        )}
      </section>
    </div>
  )
}
