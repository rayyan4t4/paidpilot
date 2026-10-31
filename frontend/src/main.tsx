import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ClientPay from './ClientPay.tsx'

const payMatch = window.location.pathname.match(/^\/pay\/(.+)$/)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {payMatch ? <ClientPay invoiceId={payMatch[1]} /> : <App />}
  </StrictMode>,
)
