import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const frontend = fileURLToPath(new URL('.', import.meta.url))
const python = process.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
    ...(process.env.CI ? {} : { channel: 'chrome' }),
  },
  webServer: [
    {
      command: `${python} backend/manage.py runserver 127.0.0.1:8000 --noreload`,
      cwd: root,
      url: 'http://127.0.0.1:8000/api/v1/schema/',
      timeout: 30000,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev',
      cwd: frontend,
      url: 'http://localhost:5173',
      timeout: 30000,
      reuseExistingServer: true,
    },
  ],
})
