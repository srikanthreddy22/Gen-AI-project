import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="bottom-right"
      toastOptions={{
        duration: 3500,
        style: {
          background: 'rgba(9,9,21,0.95)',
          color: '#e8e6f8',
          border: '1px solid rgba(124,58,237,0.3)',
          backdropFilter: 'blur(20px)',
          fontFamily: "'Outfit', sans-serif",
          fontSize: '13px',
          boxShadow: '0 0 30px rgba(124,58,237,0.2), 0 8px 32px rgba(0,0,0,0.4)',
          borderRadius: '12px',
          padding: '12px 16px',
        },
        success: { iconTheme: { primary: '#10b981', secondary: '#05050e' } },
        error: { iconTheme: { primary: '#f43f5e', secondary: '#05050e' } },
      }}
    />
  </React.StrictMode>
)
