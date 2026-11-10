import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary><App /></ErrorBoundary>
    <Toaster
      position="bottom-right"
      toastOptions={{
        duration: 3500,
        style: {
          background: 'var(--surface-glass)',
          color: 'var(--ink)',
          border: '1px solid var(--line)',
          backdropFilter: 'blur(10px) saturate(115%)',
          fontFamily: "'Manrope', sans-serif",
          fontSize: '13px',
          boxShadow: '0 10px 30px var(--panel-shadow)',
          borderRadius: 'var(--radius-sm)',
          padding: '12px 16px',
        },
        success: { iconTheme: { primary: 'var(--success)', secondary: 'var(--panel-raised)' } },
        error: { iconTheme: { primary: 'var(--danger)', secondary: 'var(--panel-raised)' } },
      }}
    />
  </React.StrictMode>
)
