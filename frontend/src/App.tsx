import { useCallback, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal, Toast } from './shared'
import { ThemeControls } from './theme'
import { ExamDetailPage, LibraryPage, ManualExamPage } from './catalog'
import { HistoryPage, PracticePage, ResultPage } from './practice'
import { PublicationDetailPage, PublicationQueuePage } from './publication'
import { ImportReviewPage, ImportsPage, TxtImportPage } from './imports'
import { OperationsPage } from './ops'

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const [confirmLogout, setConfirmLogout] = useState(false)
  const [message, setMessage] = useState('')
  const navigate = useNavigate()
  const closeLogout = useCallback(() => setConfirmLogout(false), [])

  async function leave() {
    try {
      await logout()
      setConfirmLogout(false)
      navigate('/')
    } catch {
      setMessage('Không thể đăng xuất. Vui lòng thử lại.')
    }
  }

  return <>
    <header className="topbar bg-surface text-text">
      <Link to="/" className="brand" aria-label="TestFlow, trang chủ"><span className="brand-mark" />TestFlow</Link>
      <nav aria-label="Điều hướng chính">
        <Link to="/library">Thư viện</Link>
        {user ? <>
          <Link to="/imports/new">Nhập TXT</Link>
          <Link to="/account">Tài khoản</Link>
          <Link to="/history">Lịch sử</Link>
          {(user.roles.includes('Reviewer') || user.roles.includes('Admin')) && <Link to="/publish-requests">Duyệt đề</Link>}
          {user.roles.includes('Admin') && <Link to="/ops">Vận hành</Link>}
          <button type="button" className="text-button" onClick={() => setConfirmLogout(true)}>Đăng xuất</button>
        </> : <>
          <Link to="/login">Đăng nhập</Link>
          <Link to="/register" className="header-action">Tạo tài khoản</Link>
        </>}
      </nav>
      <ThemeControls />
    </header>
    <main id="main">{children}</main>
    {message && <Toast message={message} />}
    {confirmLogout && <Modal title="Đăng xuất?" onClose={closeLogout}>
      <p>Phiên đăng nhập trên thiết bị này sẽ kết thúc.</p>
      <button type="button" className="button primary" onClick={leave}>Đăng xuất</button>
    </Modal>}
  </>
}

function Home() {
  return <section className="intro paper">
    <p className="eyebrow">KHÔNG GIAN HỌC TẬP</p>
    <h1>Đề thi rõ ràng.<br />Tiến bộ thấy được.</h1>
    <p>TestFlow giúp bạn lưu đề, luyện tập và xem lại kết quả trong một nơi.</p>
    <Link className="button primary" to="/library">Xem thư viện đề</Link>
  </section>
}

function AuthForm({ kind }: { kind: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from || '/account'
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  if (user) return <Navigate to={from} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(''); setPending(true)
    try {
      if (kind === 'register') await register(username, email, password)
      else await login(identifier, password)
      navigate(from, { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Có lỗi xảy ra. Vui lòng thử lại.')
    } finally { setPending(false) }
  }

  return <section className="auth-panel paper">
    <p className="eyebrow">TESTFLOW / TÀI KHOẢN</p>
    <h1>{kind === 'register' ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
    <p className="lede">{kind === 'register' ? 'Lưu đề và kết quả luyện tập của bạn.' : 'Tiếp tục hành trình học tập của bạn.'}</p>
    <form onSubmit={submit}>
      {kind === 'register' ? <>
        <label>Tên đăng nhập<input autoComplete="username" required maxLength={150} value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      </> : <label>Tên đăng nhập hoặc email<input autoComplete="username" required value={identifier} onChange={(event) => setIdentifier(event.target.value)} /></label>}
      <label>Mật khẩu<input type="password" autoComplete={kind === 'register' ? 'new-password' : 'current-password'} required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={pending}>{pending ? 'Đang xử lý…' : kind === 'register' ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
    </form>
    <p className="switch">{kind === 'register' ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'}{' '}
      <Link to={kind === 'register' ? '/login' : '/register'} state={{ from }}>
        {kind === 'register' ? 'Đăng nhập' : 'Tạo tài khoản'}
      </Link>
    </p>
  </section>
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="loading" role="status">Đang khôi phục phiên đăng nhập…</p>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
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
    <form className="profile-form" onSubmit={save}>
      <label>Tên hiển thị<input maxLength={160} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
      <label>Trường<input maxLength={160} value={school} onChange={(event) => setSchool(event.target.value)} /></label>
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
    <Route path="/account" element={<Protected><Account /></Protected>} />
    <Route path="/library" element={<LibraryPage />} />
    <Route path="/exams/new" element={<Protected><ManualExamPage /></Protected>} />
    <Route path="/imports" element={<Protected><ImportsPage /></Protected>} />
    <Route path="/imports/new" element={<Protected><TxtImportPage /></Protected>} />
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
