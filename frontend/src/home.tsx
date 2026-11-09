import { useState, type FormEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'
import heroDashboard from './assets/hero-dashboard.webp'
import { ExamCard, type ExamCardData } from './exam-card'
export { DeckMark } from './exam-art'

type HomeExam = ExamCardData & { chapter_count: number }
type Page<T> = { count: number; next: string | null; results: T[] }
type Subject = { code: string; name: string }
type RecentSession = {
  id: string; exam_title: string; status: string; total_questions: number; answered_questions: number
}
const featuredSubjects = ['Toán', 'Vật lý', 'Hóa học', 'Sinh học', 'Tiếng Anh', 'Ngữ văn', 'Lịch sử', 'Địa lý']

function Icon({ kind, size = 28 }: { kind: string; size?: number }) {
  const glyphs: Record<string, ReactNode> = {
    clock: <><circle cx="16" cy="16" r="12" /><path d="M16 8v9l6 3" /></>,
    book: <><path d="M16 28c-4-3-8-4-13-3V6c5-1 9 0 13 3 4-3 8-4 13-3v19c-5-1-9 0-13 3ZM16 9v19" /></>,
    document: <><path d="M8 3h11l6 6v20H8zM19 3v7h6M12 16h9M12 21h9" /></>,
    play: <path d="m12 8 12 8-12 8V8Z" />,
    calculator: <><rect x="7" y="4" width="18" height="24" rx="2" /><path d="M11 9h10M12 15h1m5 0h1m-7 5h1m5 0h1m-7 5h1m5 0h1" /></>,
    physics: <><ellipse cx="16" cy="16" rx="12" ry="4" transform="rotate(45 16 16)" /><ellipse cx="16" cy="16" rx="12" ry="4" transform="rotate(-45 16 16)" /><circle cx="16" cy="16" r="2" fill="currentColor" /></>,
    chemistry: <><path d="M12 4h8M14 4v9L7 25a2 2 0 0 0 2 3h14a2 2 0 0 0 2-3l-7-12V4M10 22h12" /></>,
    biology: <><path d="M27 5C13 5 6 12 6 21c0 4 3 6 7 6 9 0 14-8 14-22ZM9 24c5-6 9-10 15-13" /></>,
    language: <><path d="M5 25 12 6l7 19M8 18h8M20 15h8M24 15v11M20 26h8" /></>,
    literature: <><path d="M16 27c-4-3-8-4-12-3V7c5-1 9 0 12 3 3-3 7-4 12-3v17c-4-1-8 0-12 3ZM16 10v17M8 14h4m8 0h4" /></>,
    history: <><path d="M4 12h24M6 12l10-7 10 7M8 12v13m5-13v13m6-13v13m5-13v13M4 27h24" /></>,
    geography: <><circle cx="16" cy="16" r="12" /><path d="M4 16h24M16 4c-7 7-7 17 0 24M16 4c7 7 7 17 0 24" /></>,
  }
  return <svg viewBox="0 0 32 32" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{glyphs[kind] || glyphs.book}</svg>
}

function subjectIcon(name: string) {
  if (name.startsWith('Toán')) return 'calculator'
  if (name.startsWith('Vật')) return 'physics'
  if (name.startsWith('Hóa')) return 'chemistry'
  if (name.startsWith('Sinh')) return 'biology'
  if (name.startsWith('Tiếng')) return 'language'
  if (name.startsWith('Ngữ')) return 'literature'
  if (name.startsWith('Lịch')) return 'history'
  return 'geography'
}

export function Home() {
  const { api, user, loading } = useAuth()
  const [input, setInput] = useState('')
  const [search, setSearch] = useState('')
  const [subject, setSubject] = useState('')
  const subjects = useQuery({ queryKey: ['subjects'], queryFn: () => api<Subject[]>('/subjects/') })
  const exams = useQuery({
    queryKey: ['home-exams', user?.id, search, subject],
    queryFn: () => api<Page<HomeExam>>(`/exams/?${new URLSearchParams({ page: '1', ...(search ? { q: search } : {}), ...(subject ? { subject } : {}) })}`),
    enabled: !loading,
  })
  const recent = useQuery({
    queryKey: ['home-recent-session', user?.id],
    queryFn: () => api<Page<RecentSession>>('/practice/sessions/history/?status=IN_PROGRESS'),
    enabled: !loading && !!user,
  })
  const inProgress = recent.data?.results || []
  const featured = featuredSubjects.map((name) => subjects.data?.find((item) => item.name === name || (name === 'Vật lý' && item.name === 'Vật lí') || (name === 'Địa lý' && item.name === 'Địa lí'))).filter((item): item is Subject => !!item)

  function submit(event: FormEvent) {
    event.preventDefault()
    setSearch(input.trim())
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById('home-library')?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
  }

  return <div className="home-page">
    <section className="home-hero" aria-labelledby="home-title">
      <img className="home-hero-image" src={heroDashboard} alt="" />
      <div className="home-hero-content">
        <h1 id="home-title">Hôm nay, bạn muốn<br />luyện tập gì?</h1>
        <p>Tìm kiếm đề thi phù hợp và tiếp tục hành trình học tập của bạn.</p>
        <form className="home-search" role="search" onSubmit={submit}>
          <label className="visually-hidden" htmlFor="home-query">Tìm bộ đề</label>
          <div className="home-search-box">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7" stroke="currentColor" strokeWidth="2" /><path d="m16 16 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
            <input id="home-query" type="search" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Tìm đề thi, môn học, chủ đề..." />
            <button type="submit">Tìm đề</button>
          </div>
        </form>
      </div>
    </section>
    <section className="home-resume" aria-labelledby="home-resume-title">
      <div className="home-resume-intro"><Icon kind="clock" size={38} /><div><h2 id="home-resume-title">Tiếp tục học tập</h2><p>{user ? recent.isPending ? 'Đang tải bài học…' : `${recent.data?.count || 0} bài đang làm dở` : 'Đăng nhập để lưu tiến độ'}</p></div></div>
      {user && inProgress.length > 0 ? <div className="home-resume-list">{inProgress.slice(0, 2).map((session) => {
        const progress = session.total_questions ? Math.min(100, Math.round(session.answered_questions / session.total_questions * 100)) : 0
        return <Link className="home-resume-item" key={session.id} to={`/practice/${session.id}`} aria-label={`Tiếp tục ${session.exam_title}, ${progress}% hoàn thành`}>
          <span className="home-resume-document"><Icon kind="document" size={29} /></span>
          <span className="home-resume-detail"><strong>{session.exam_title}</strong><span className="home-progress"><span className="home-progress-track"><span style={{ width: `${progress}%` }} /></span><span>{progress}%</span></span></span>
          <span className="home-resume-play"><Icon kind="play" size={22} /></span>
        </Link>
      })}</div> : <div className="home-resume-empty">{user ? recent.isPending ? 'Đang tải…' : 'Chọn một đề trong thư viện để bắt đầu.' : 'Bài làm của bạn sẽ hiện ở đây sau khi đăng nhập.'}</div>}
      {user && <Link className="home-resume-all" to="/history">Xem tất cả <span aria-hidden="true">→</span></Link>}
    </section>
    <section className="home-library" id="home-library" aria-labelledby="home-library-title">
      <div className="home-library-heading"><div><Icon kind="book" size={39} /><h2 id="home-library-title">Đề nổi bật</h2></div><Link to="/library">Xem thêm <span aria-hidden="true">→</span></Link></div>
      <div className="home-subjects" role="group" aria-label="Lọc theo môn học">
        <button type="button" className={!subject ? 'is-active' : ''} aria-pressed={!subject} onClick={() => setSubject('')}>Tất cả</button>
        {featured.map((item) => <button type="button" key={item.code} className={subject === item.code ? 'is-active' : ''} aria-pressed={subject === item.code} onClick={() => setSubject(item.code)}><Icon kind={subjectIcon(item.name)} size={24} />{item.name}</button>)}
      </div>
      {exams.isPending && <div role="status" className="home-loading">Đang tải đề thi…</div>}
      {exams.isError && <p role="alert">{exams.error.message} <button type="button" onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data?.count === 0 && <div className="home-empty paper"><p>{search || subject ? 'Không tìm thấy bộ đề phù hợp.' : 'Chưa có đề thi nào trong thư viện.'}</p><Link to="/library">Mở thư viện đề →</Link></div>}
      {exams.data && exams.data.count > 0 && <div className="home-deck-grid library-results">
        {exams.data.results.map((exam) => <ExamCard key={exam.id} exam={exam} />)}
      </div>}
      {exams.data?.next && <p className="home-more"><Link to="/library">Xem thêm trong thư viện →</Link></p>}
    </section>
  </div>
}
