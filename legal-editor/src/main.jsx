import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import KararatlasApp from './MevzubaseLanding.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <KararatlasApp />
  </StrictMode>,
)
