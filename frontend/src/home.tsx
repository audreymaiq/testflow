import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'
import heroStudyDesk from './assets/hero-study-desk.webp'
import { DeckMark } from './exam-art'
export { DeckMark } from './exam-art'

type HomeExam = {
  id: string; title: string; subtitle: string; icon: string; color: string; subject: string
  chapter_count: number; question_count: number; visibility: string; is_system_sample: boolean
}
type Page<T> = { count: number; next: string | null; results: T[] }
type StudyStats = { total_sessions: number; completed_sessions: number; timed_sessions: number; practice_sessions: number }
type RecentSession = { id: string; exam_title: string; mode: 'TIMED' | 'PRACTICE'; status: string }

export function Home() {
  const { api, user, loading } = useAuth()
  const [input, setInput] = useState('')
  const [search, setSearch] = useState('')
  const exams = useQuery({
    queryKey: ['home-exams', user?.id, search],
    queryFn: () => api<Page<HomeExam>>(`/exams/?${new URLSearchParams({ page: '1', ...(search ? { q: search } : {}) })}`),
    enabled: !loading,
  })
  const stats = useQuery({
    queryKey: ['home-study-stats', user?.id],
    queryFn: () => api<StudyStats>('/practice/stats/'),
    enabled: !loading && !!user,
  })
  const recent = useQuery({
    queryKey: ['home-recent-session', user?.id],
    queryFn: () => api<Page<RecentSession>>('/practice/sessions/history/'),
    enabled: !loading && !!user,
  })
  const latest = recent.data?.results[0]
  const latestPath = latest?.status === 'IN_PROGRESS'
    ? `/practice/${latest.id}` : latest ? `/practice/${latest.id}/result` : '/history'

  function submit(event: FormEvent) {
    event.preventDefault()
    setSearch(input.trim())
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById('home-library')?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
  }

  return <div className="home-page">
    <section className="home-hero paper" aria-labelledby="home-title">
      <div className="home-hero-main">
        <p className="eyebrow">TESTFLOW / HỌC THEO ĐỀ</p>
        <h1 id="home-title">Chọn đề.<br />Bắt đầu học.</h1>
        <form className="home-search" role="search" onSubmit={submit}>
          <label htmlFor="home-query">Tìm bộ đề</label>
          <div className="home-search-box">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.8" />
              <path d="m15.5 15.5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <input id="home-query" type="search" value={input} onChange={(event) => setInput(event.target.value)}
              placeholder="Tên đề, môn học…" />
            <button className="button primary" type="submit">Tìm đề</button>
          </div>
        </form>
        <Link className="home-secondary-link" to={user ? '/history' : '/register'}>
          {user ? 'Xem tiến độ học tập' : 'Tạo tài khoản để lưu tiến độ'} <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <div className="home-visual" aria-hidden="true"><img src={heroStudyDesk} alt="" /></div>
    </section>
    {user && <aside className="home-study-panel is-personal" aria-label="Tiến độ học tập">
        <p className="eyebrow">PHIẾU HỌC TẬP</p>
          <p className="home-study-greeting">Chào {user.display_name || user.username},</p>
          {stats.data ? <>
            <p className="home-study-total"><strong>{stats.data.completed_sessions}</strong><span>lượt đã hoàn thành</span></p>
            <dl className="home-study-breakdown">
              <div><dt>Ôn tập</dt><dd>{stats.data.practice_sessions}</dd></div>
              <div><dt>Thi thử</dt><dd>{stats.data.timed_sessions}</dd></div>
            </dl>
          </> : <p className="home-study-placeholder">{stats.isPending ? 'Đang tải tiến độ…' : 'Xem các lượt học trong lịch sử.'}</p>}
          {latest && <Link className="home-continue" to={latestPath}>
            <span className="eyebrow">{latest.status === 'IN_PROGRESS' ? 'TIẾP TỤC BÀI ĐANG LÀM' : 'LƯỢT HỌC GẦN NHẤT'}</span>
            <strong>{latest.exam_title}</strong>
            <span>{latest.status === 'IN_PROGRESS' ? 'Tiếp tục làm bài' : 'Xem kết quả'} <span aria-hidden="true">↗</span></span>
          </Link>}
    </aside>}
    <section className="home-library" id="home-library" aria-labelledby="home-library-title">
      <div className="section-heading">
        <div><p className="eyebrow">DANH MỤC HỌC TẬP</p><h2 id="home-library-title">Thư viện đề</h2></div>
        <Link to="/library">Xem toàn bộ thư viện</Link>
      </div>
      {exams.isPending && <div role="status" className="home-loading">Đang tải bộ đề…</div>}
      {exams.isError && <p role="alert">{exams.error.message} <button type="button" onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data?.count === 0 && <div className="home-empty paper"><p>{search ? 'Không tìm thấy bộ đề phù hợp.' : 'Chưa có bộ đề nào. Hãy tạo đề đầu tiên trong thư viện.'}</p>
        <Link to={search ? '/library' : '/imports/new'}>{search ? 'Dùng bộ lọc trong thư viện' : 'Nhập bộ câu hỏi TXT'} <span aria-hidden="true">↗</span></Link></div>}
      {exams.data && exams.data.count > 0 && <>
        <p className="result-count">{exams.data.count} bộ đề{search && ` cho “${search}”`}</p>
        <div className="home-deck-grid">
          {exams.data.results.map((exam) => <Link className="home-deck paper" key={exam.id} to={`/exams/${exam.id}`}>
            <span className="home-deck-top"><DeckMark title={exam.title} icon={exam.icon} color={exam.color} /></span>
            <span className="home-deck-copy">
              <strong>{exam.title} {exam.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</strong>
              {exam.subtitle && <small>{exam.subtitle}</small>}
              <span className="home-deck-meta"><span>{exam.subject}</span><span>{exam.chapter_count} chương · {exam.question_count} câu</span></span>
            </span>
            <span className="home-deck-foot"><span className="home-deck-visibility">{exam.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</span>
              <span className="home-deck-open">Xem bộ đề <span aria-hidden="true">↗</span></span></span>
          </Link>)}
        </div>
        {exams.data.next && <p><Link to="/library">Xem thêm trong thư viện</Link></p>}
      </>}
    </section>
  </div>
}
