module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', surface: 'var(--surface)', text: 'var(--text)',
        muted: 'var(--muted)', accent: 'var(--accent)', border: 'var(--border)',
      },
    },
  },
  plugins: [],
}
