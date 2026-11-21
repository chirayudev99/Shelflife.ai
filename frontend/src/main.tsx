import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@/lib/env'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'
import { Analytics } from "@vercel/analytics/next"

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <App />
      <Analytics />
      <Toaster position="top-center" richColors />
    </TooltipProvider>
  </StrictMode>,
)
