import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './style.css'

// React owns the page content inside the root element.
createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
