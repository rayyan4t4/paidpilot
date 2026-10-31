import { useCallback, useEffect, useMemo, useState } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community'
import { api, formatPlan, type Invoice } from './api'

ModuleRegistry.registerModules([AllCommunityModule])

const gridTheme = themeQuartz.withParams({ accentColor: '#0a6c4f', borderRadius: 10 })

function isOverdue(inv: Invoice) {
  return inv.status === 'SENT' && inv.due_date < new Date().toISOString().slice(0, 10)
}

export default function App() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [mock, setMock] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<(Invoice & { messages?: { role: string; body: string }[] }) | null>(null)
  const [clientMsg, setClientMsg] = useState('')

  const load = useCallback(async () => {
    try {
      setInvoices(await api.listInvoices())
      setMock((await api.health()).mock_mode)
    } catch {
      setError('Backend not reachable. Start it with: uvicorn app.main:app --port 8000')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const stats = useMemo(() => {
    const outstanding = invoices.filter(i => i.status === 'SENT').reduce((s, i) => s + i.amount, 0)
    const collected = invoices.filter(i => i.status === 'PAID').reduce((s, i) => s + i.amount, 0)
    const overdue = invoices.filter(isOverdue).length
    return { outstanding, collected, overdue }
  }, [invoices])

  const create = async () => {
    if (!text.trim()) return
    setBusy(true); setError('')
    try {
      await api.fromText(text.trim())
      setText('')
      await load()
    } catch (e) { setError(String((e as Error).message)) }
    setBusy(false)
  }

  const openInvoice = async (inv: Invoice) => setSelected(await api.invoice(inv.id))

  const remind = async (inv: Invoice) => { await api.remind(inv.id); await load(); if (selected?.id === inv.id) openInvoice(inv) }
  const pay = async (inv: Invoice) => { await api.simulatePay(inv.id); await load(); if (selected?.id === inv.id) openInvoice(inv) }
  const sendClientMsg = async () => {
    if (!selected || !clientMsg.trim()) return
    await api.clientMessage(selected.id, clientMsg.trim())
    setClientMsg('')
    openInvoice(selected)
    load()
  }

  const columnDefs = useMemo<ColDef<Invoice>[]>(() => [
    { field: 'client_name', headerName: 'Client', flex: 1.2 },
    { field: 'description', headerName: 'Work', flex: 1.7 },
    { field: 'amount', headerName: 'Amount', flex: 0.8, valueFormatter: p => `$${Number(p.value).toFixed(2)}` },
    { field: 'due_date', headerName: 'Due', flex: 0.8 },
    { field: 'status', headerName: 'Status', flex: 0.8, cellStyle: p => ({ color: p.value === 'PAID' ? '#0a6c4f' : isOverdue(p.data!) ? '#b3261e' : '#7a5b00', fontWeight: 600 }) },
    { field: 'reminders', headerName: 'Reminders', flex: 0.7 },
    {
      headerName: '', width: 262, sortable: false, filter: false,
      cellRenderer: (p: { data: Invoice }) => (
        <span style={{ display: 'flex', gap: 6 }}>
          <button onClick={() => openInvoice(p.data)}>Thread</button>
          {p.data.status !== 'PAID' && <button onClick={() => remind(p.data)}>Remind</button>}
          {p.data.status !== 'PAID' && <button onClick={() => pay(p.data)}>Mark paid</button>}
        </span>
      ),
    },
  ], [selected])

  return (
    <div className="page">
      <header>
        <h1>PaidPilot</h1>
        <p>The AI agent that invoices, follows up, negotiates — and gets freelancers paid via PayPal.</p>
        {mock && <span className="badge">Demo mode — connect PayPal sandbox keys to go live</span>}
      </header>

      <section className="stats">
        <div><strong>${stats.outstanding.toFixed(2)}</strong><span>Outstanding</span></div>
        <div><strong>{stats.overdue}</strong><span>Overdue</span></div>
        <div><strong>${stats.collected.toFixed(2)}</strong><span>Collected</span></div>
      </section>

      <section className="create">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && create()}
          placeholder='Try: "Website redesign for Sara Malik, $1,200, due in 10 days"'
        />
        <button onClick={create} disabled={busy}>{busy ? 'Working…' : 'Create & send invoice'}</button>
      </section>
      {error && <p className="error">{error}</p>}
      {invoices.length === 0 && !error && (
        <p><button onClick={async () => { await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/api/demo/seed`, { method: 'POST' }); load() }}>Load demo data</button></p>
      )}

      <div className="grid-wrap">
        <AgGridReact theme={gridTheme} rowData={invoices} columnDefs={columnDefs} rowHeight={44} headerHeight={40} />
      </div>

      {selected && (
        <aside className="drawer">
          <button className="close" onClick={() => setSelected(null)}>×</button>
          <h2>{selected.client_name} — ${selected.amount.toFixed(2)}</h2>
          <p>{selected.description} · due {selected.due_date} · {selected.status}</p>
          {selected.pay_link && <p><a href={selected.pay_link} target="_blank" rel="noreferrer">PayPal invoice link</a></p>}
          <p><a href={`/pay/${selected.id}`} target="_blank" rel="noreferrer">Open the client payment page</a></p>
          {formatPlan(selected.agreed_plan) && <p className="plan">Agreed plan: {formatPlan(selected.agreed_plan)}</p>}
          <div className="thread">
            {(selected.messages || []).map((m, i) => (
              <div key={i} className={`msg ${m.role}`}><span>{m.role}</span>{m.body}</div>
            ))}
          </div>
          <div className="reply">
            <input value={clientMsg} onChange={e => setClientMsg(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendClientMsg()} placeholder='Reply as the client, e.g. "Can I pay half now?"' />
            <button onClick={sendClientMsg}>Send</button>
          </div>
        </aside>
      )}
    </div>
  )
}
