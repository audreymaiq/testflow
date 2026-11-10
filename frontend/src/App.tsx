import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { request } from './api'
import { useAuth } from './auth'
import { TaxonomyEntry } from './taxonomy'
import { Modal, Toast } from './shared'
import { ModeControl } from './theme'
import { ExamDetailPage, LibraryPage, ManualExamPage } from './catalog'
import { HistoryPage, PracticePage, ResultPage } from './practice'
import { PublicationDetailPage, PublicationQueuePage } from './publication'
import { AddExamPage, ImportReviewPage, ImportsPage, TxtImportPage } from './imports'
import { DocumentImportPage } from './document-import'
import { OperationsPage } from './ops'
import { Home } from './home'

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [message, setMessage] = useState('')
  const navigate = useNavigate()
  const headerRef = useRef<HTMLElement>(null)
  const closeLogout = useCallback(() => { if (!leaving) setConfirmLogout(false) }, [leaving])
  const closeMessage = useCallback(() => setMessage(''), [])

  useEffect(() => {
    const header = headerRef.current
    if (!header) return
    const syncHeight = () => document.documentElement.style.setProperty('--header-height', `${header.getBoundingClientRect().height}px`)
    syncHeight()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(syncHeight)
    observer?.observe(header)
    window.addEventListener('resize', syncHeight)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', syncHeight)
      document.documentElement.style.removeProperty('--header-height')
    }
  }, [])

  async function leave() {
    if (leaving) return
    setLeaving(true)
    navigate('/', { replace: true })
    try {
      await logout()
      setConfirmLogout(false)
    } catch {
      setMessage('Không thể đăng xuất. Vui lòng thử lại.')
    } finally { setLeaving(false) }
  }

  return <>
    <a className="skip-link" href="#main">Bỏ qua điều hướng</a>
    <header ref={headerRef} className="topbar topbar-dashboard bg-surface text-text">
      <div className="topbar-inner">
      <Link to="/" className="brand" aria-label="TestFlow, trang chủ">
        <svg className="brand-symbol" viewBox="0 0 48 48" width="38" height="38" fill="none" aria-hidden="true">
          <path d="M24 41c-5.6-4.3-11.4-5.9-19-5.6V9.5C13 8.7 19 10.8 24 15v26Z" fill="#00A8B5" />
          <path d="M24 41c5.6-4.3 11.4-5.9 19-5.6V9.5C35 8.7 29 10.8 24 15v26Z" fill="#0757D7" />
          <path d="M24 15v26" stroke="#FFFFFF" strokeWidth="1.6" />
        </svg>
        <span className="brand-wordmark">TestFlow</span>
      </Link>
      <nav aria-label="Điều hướng chính">
        <NavLink to="/" end>Trang chủ</NavLink>
        <NavLink to="/library">Thư viện</NavLink>
        {user ? <NavLink to="/history">Kết quả</NavLink> : <Link to="/login">Kết quả</Link>}
      </nav>
      <div className="header-dashboard-actions">
        {user ? <>
          <details className="header-popover header-notifications"><summary aria-label="Thông báo"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-2.5 7.5-2.5 9h17C20.5 15.5 18 15 18 8ZM10 20h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg></summary><div className="header-popover-panel" role="status">Chưa có thông báo.</div></details>
          <details className="header-popover header-account"><summary aria-label="Mở menu tài khoản"><span className="header-avatar" aria-hidden="true">{(user.display_name || user.username).slice(0, 1).toUpperCase()}</span><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m4 7 6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></summary>
            <div className="header-popover-panel"><Link to="/account">Tài khoản</Link><Link to="/add-exam">Thêm đề</Link>{(user.roles.includes('Reviewer') || user.roles.includes('Admin')) && <Link to="/publish-requests">Duyệt đề</Link>}{user.roles.includes('Admin') && <Link to="/ops">Vận hành</Link>}<ModeControl /><button type="button" onClick={() => setConfirmLogout(true)}>Đăng xuất</button></div>
          </details>
        </> : <><Link className="header-guest-link" to="/login">Đăng nhập</Link><Link className="header-guest-action" to="/register">Tạo tài khoản</Link><ModeControl /></>}
      </div>
      </div>
    </header>
    <main id="main">{children}</main>
    {message && <Toast key={message} message={message} onClose={closeMessage} />}
    {confirmLogout && <Modal title="Đăng xuất?" onClose={closeLogout}>
      <p>Phiên đăng nhập trên thiết bị này sẽ kết thúc.</p>
      <button type="button" className="button primary" disabled={leaving} onClick={leave}>{leaving ? 'Đang đăng xuất…' : 'Đăng xuất'}</button>
    </Modal>}
  </>
}

function AuthForm({ kind }: { kind: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const intent = location.state as { from?: unknown; practiceMode?: unknown; resetDone?: boolean } | null
  const requestedFrom = intent?.from
  const from = typeof requestedFrom === 'string' && requestedFrom.startsWith('/')
    && !requestedFrom.startsWith('//') && !requestedFrom.includes('\\')
    && !['/login', '/register'].includes(requestedFrom)
    ? requestedFrom : '/account'
  const practiceMode = /^\/exams\/[0-9a-f-]{36}$/i.test(from)
    && (intent?.practiceMode === 'TIMED' || intent?.practiceMode === 'PRACTICE')
    ? intent.practiceMode : null
  const destinationState = practiceMode ? { resumePractice: practiceMode } : null
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [loginStep, setLoginStep] = useState<'identifier' | 'password'>('identifier')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  if (user) return <Navigate to={from} state={destinationState} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (kind === 'login' && loginStep === 'identifier') {
      if (identifier.trim()) setLoginStep('password')
      return
    }
    setError(''); setPending(true)
    try {
      if (kind === 'register') await register(username, email, password)
      else await login(identifier, password)
      navigate(from, { replace: true, state: destinationState })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Có lỗi xảy ra. Vui lòng thử lại.')
    } finally { setPending(false) }
  }

  return <section className="auth-panel paper">
    <p className="eyebrow">TESTFLOW / TÀI KHOẢN</p>
    <h1>{kind === 'register' ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
    <p className="lede">{kind === 'register' ? 'Lưu đề và kết quả luyện tập của bạn.' : 'Tiếp tục hành trình học tập của bạn.'}</p>
    {kind === 'login' && intent?.resetDone && <p role="status">Mật khẩu đã được đổi. Hãy đăng nhập lại.</p>}
    <form onSubmit={submit}>
      {kind === 'register' ? <>
        <label>Tên đăng nhập<input autoComplete="username" required maxLength={150} value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      </> : loginStep === 'identifier'
        ? <label>Tên đăng nhập hoặc email<input autoComplete="username" required autoFocus value={identifier} onChange={(event) => setIdentifier(event.target.value)} /></label>
        : <p className="login-identity">{identifier} <button type="button" className="text-button" onClick={() => { setLoginStep('identifier'); setPassword(''); setError('') }}>Đổi tài khoản</button></p>}
      {(kind === 'register' || loginStep === 'password') &&
        <label>Mật khẩu<input type="password" autoComplete={kind === 'register' ? 'new-password' : 'current-password'} required autoFocus={kind === 'login'} minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={pending}>{pending ? 'Đang xử lý…' : kind === 'register' ? 'Tạo tài khoản' : loginStep === 'identifier' ? 'Tiếp tục' : 'Đăng nhập'}</button>
    </form>
    {kind === 'login' && <p><Link to="/forgot-password">Quên mật khẩu?</Link></p>}
    <p className="switch">{kind === 'register' ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'}{' '}
      <Link to={kind === 'register' ? '/login' : '/register'} state={{ from, practiceMode }}>
        {kind === 'register' ? 'Đăng nhập' : 'Tạo tài khoản'}
      </Link>
    </p>
  </section>
}

function PasswordResetRequestPage() {
  const [email, setEmail] = useState('')
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true); setError('')
    try {
      await request('/auth/password/reset/', {
        method: 'POST', body: JSON.stringify({ email }),
      })
      setSent(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể gửi yêu cầu. Vui lòng thử lại.')
    } finally { setPending(false) }
  }

  return <section className="auth-panel paper">
    <p className="eyebrow">TESTFLOW / TÀI KHOẢN</p>
    <h1>Đặt lại mật khẩu</h1>
    {sent ? <p role="status">Nếu email có tài khoản, chúng tôi đã gửi liên kết đặt lại mật khẩu.</p>
      : <form onSubmit={submit}>
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button type="submit" className="button primary" disabled={pending}>{pending ? 'Đang gửi…' : 'Gửi liên kết'}</button>
      </form>}
    <p><Link to="/login">Về đăng nhập</Link></p>
  </section>
}

function PasswordResetConfirmPage() {
  const { uid, token } = useParams()
  const navigate = useNavigate()
  const { clearSession } = useAuth()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirmation) { setError('Hai mật khẩu chưa khớp.'); return }
    setPending(true); setError('')
    try {
      await request('/auth/password/reset/confirm/', {
        method: 'POST', body: JSON.stringify({ uid, token, password }),
      })
      clearSession()
      navigate('/login', { replace: true, state: { resetDone: true } })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể đổi mật khẩu. Vui lòng thử lại.')
    } finally { setPending(false) }
  }

  return <section className="auth-panel paper">
    <p className="eyebrow">TESTFLOW / TÀI KHOẢN</p>
    <h1>Mật khẩu mới</h1>
    <form onSubmit={submit}>
      <label>Mật khẩu mới<input type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <label>Xác nhận mật khẩu<input type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={pending}>{pending ? 'Đang lưu…' : 'Đổi mật khẩu'}</button>
    </form>
    <p><Link to="/forgot-password">Yêu cầu liên kết mới</Link></p>
  </section>
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="loading" role="status">Đang khôi phục phiên đăng nhập…</p>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname + location.search + location.hash }} replace />
  return children
}

function Account() {
  const { user, updateProfile } = useAuth()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [school, setSchool] = useState(user?.school || '')
  const [grade, setGrade] = useState(user?.grade || '')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')

  async function save(event: FormEvent) {
    event.preventDefault(); setPending(true); setMessage('')
    try {
      await updateProfile({ display_name: displayName, school, grade })
      setMessage('Đã lưu hồ sơ.')
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Không thể lưu hồ sơ.')
    } finally { setPending(false) }
  }

  return <section className="account-panel paper">
    <p className="eyebrow">HỒ SƠ CỦA BẠN</p>
    <h1>Xin chào, {user?.display_name || user?.username}</h1>
    <dl><div><dt>Email</dt><dd>{user?.email}</dd></div><div><dt>Vai trò</dt><dd>{user?.roles.join(', ')}</dd></div></dl>
    <p>Tra cứu tên trường đã có. Nếu chưa có tên phù hợp, bạn có thể tự tạo tên mới.</p>
    <form className="profile-form" onSubmit={save}>
      <label>Tên hiển thị<input maxLength={160} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
      <TaxonomyEntry kind="SCHOOL" label="Trường" value={school} onChange={setSchool} />
      <label>Lớp<input maxLength={20} value={grade} onChange={(event) => setGrade(event.target.value)} /></label>
      <button type="submit" className="button primary" disabled={pending}>{pending ? 'Đang lưu…' : 'Lưu hồ sơ'}</button>
      {message && <p role="status">{message}</p>}
    </form>
  </section>
}

export default function App() {
  return <Shell><Routes>
    <Route path="/" element={<Home />} />
    <Route path="/login" element={<AuthForm kind="login" />} />
    <Route path="/register" element={<AuthForm kind="register" />} />
    <Route path="/forgot-password" element={<PasswordResetRequestPage />} />
    <Route path="/reset-password/:uid/:token" element={<PasswordResetConfirmPage />} />
    <Route path="/account" element={<Protected><Account /></Protected>} />
    <Route path="/library" element={<LibraryPage />} />
    <Route path="/add-exam" element={<Protected><AddExamPage /></Protected>} />
    <Route path="/exams/new" element={<Protected><ManualExamPage /></Protected>} />
    <Route path="/imports" element={<Protected><ImportsPage /></Protected>} />
    <Route path="/imports/new" element={<Protected><TxtImportPage /></Protected>} />
    <Route path="/imports/document/new" element={<Protected><DocumentImportPage /></Protected>} />
    <Route path="/imports/:jobId" element={<Protected><ImportReviewPage /></Protected>} />
    <Route path="/exams/:id" element={<ExamDetailPage />} />
    <Route path="/practice/:sessionId" element={<Protected><PracticePage /></Protected>} />
    <Route path="/practice/:sessionId/result" element={<Protected><ResultPage /></Protected>} />
    <Route path="/history" element={<Protected><HistoryPage /></Protected>} />
    <Route path="/publish-requests" element={<Protected><PublicationQueuePage /></Protected>} />
    <Route path="/publish-requests/:requestId" element={<Protected><PublicationDetailPage /></Protected>} />
    <Route path="/ops" element={<Protected><OperationsPage /></Protected>} />
    <Route path="*" element={<section className="paper not-found"><h1>Không tìm thấy trang</h1><Link to="/">Về trang chủ</Link></section>} />
  </Routes></Shell>
}
