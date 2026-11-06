import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const frontend = fileURLToPath(new URL('.', import.meta.url))
const python = process.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python'
const mailDir = process.env.TESTFLOW_E2E_MAIL_DIR || mkdtempSync(join(tmpdir(), 'testflow-e2e-mail-'))
process.env.TESTFLOW_E2E_MAIL_DIR = mailDir

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:15173',
    browserName: 'chromium',
    ...(process.env.CI ? {} : { channel: 'chrome' }),
  },
  webServer: [
    {
      command: `${python} backend/manage.py runserver 127.0.0.1:18000 --noreload`,
      cwd: root,
      url: 'http://127.0.0.1:18000/api/v1/schema/',
      timeout: 30000,
      reuseExistingServer: false,
      env: {
        CORS_ALLOWED_ORIGINS: 'http://localhost:15173', THROTTLE_REGISTER: '100/min',
        CELERY_TASK_ALWAYS_EAGER: '1',
        EMAIL_BACKEND: 'django.core.mail.backends.filebased.EmailBackend',
        EMAIL_FILE_PATH: mailDir, PUBLIC_WEB_ORIGIN: 'http://localhost:15173',
      },
    },
    {
      command: 'npm run dev -- --port 15173 --strictPort',
      cwd: frontend,
      url: 'http://localhost:15173',
      timeout: 30000,
      reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://localhost:18000/api/v1' },
    },
  ],
})
