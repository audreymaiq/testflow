import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/vietnamese-400.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/vietnamese-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/vietnamese-400.css'
import '@fontsource/literata/latin-400.css'
import '@fontsource/literata/vietnamese-400.css'
import '../../design/tokens.css'
import './style.css'
import { AuthProvider } from './auth'
import App from './App'
import { ApiError } from './api'

const router = createBrowserRouter([{ path: '*', element: <App /> }])

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (attempt, error) => error instanceof ApiError && error.status >= 400 && error.status < 500
        ? false : attempt < 2,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider><RouterProvider router={router} /></AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
