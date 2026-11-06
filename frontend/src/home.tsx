import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'
import answerOrbit from './assets/answer-orbit.svg'

type HomeExam = {
  id: string; title: string; subtitle: string; icon: string; color: string; subject: string
  chapter_count: number; question_count: number; visibility: string; is_system_sample: boolean
}
type Page<T> = { count: number; next: string | null; results: T[] }
type StudyStats = { total_sessions: number; completed_sessions: number; timed_sessions: number; practice_sessions: number }
type RecentSession = { id: string; exam_title: string; mode: 'TIMED' | 'PRACTICE'; status: string }

export function DeckMark({ title, icon, color }: Pick<HomeExam, 'title' | 'icon' | 'color'>) {
  const legacyEye = icon.replace(/\uFE0F/g, '') === '👁'
  return <span className="home-deck-mark" aria-hidden="true"
    style={/^#[0-9a-fA-F]{6}$/.test(color) ? { borderColor: color } : undefined}>
    {legacyEye ? <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M3 16c3.5-5 7.8-7.5 13-7.5S25.5 11 29 16c-3.5 5-7.8 7.5-13 7.5S6.5 21 3 16Z" />
      <circle cx="16" cy="16" r="3.5" />
    </svg> : title.trim().slice(0, 2).toLocaleUpperCase('vi-VN')}
  </span>
}

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
        <p className="lede">Tìm một bộ đề theo tên hoặc môn học, rồi chọn thi có giờ hoặc ôn tập theo từng câu.</p>
        <form className="home-search" role="search" onSubmit={submit}>
          <label htmlFor="home-query">Tìm bộ đề</label>
          <input id="home-query" type="search" value={input} onChange={(event) => setInput(event.target.value)}
            placeholder="Tên đề, môn học…" />
          <button className="button primary" type="submit">Tìm đề</button>
        </form>
        <Link className="home-secondary-link" to={user ? '/history' : '/register'}>
          {user ? 'Xem tiến độ học tập' : 'Tạo tài khoản để lưu tiến độ'} <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <div className="home-visual" aria-hidden="true"><img src={answerOrbit} alt="" /></div>
    </section>
    <aside className={`home-study-panel ${user ? 'is-personal' : 'is-intro'}`} aria-label={user ? 'Tiến độ học tập' : 'Cách bắt đầu'}>
        <p className="eyebrow">{user ? 'PHIẾU HỌC TẬP' : 'CÁCH HỌC'}</p>
        {user ? <>
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
        </> : <>
          <p className="home-study-intro">Hai cách học trên cùng một bộ đề có đáp án.</p>
          <dl className="home-study-modes">
            <div><dt>01 / THI CÓ GIỜ</dt><dd>Làm trọn bài; xem đáp án sau khi nộp.</dd></div>
            <div><dt>02 / ÔN TẬP</dt><dd>Nhận phản hồi theo từng câu để hiểu phần chưa chắc.</dd></div>
          </dl>
          <Link to="/library" className="home-study-link">Mở thư viện <span aria-hidden="true">↗</span></Link>
        </>}
    </aside>
    <section className="home-library" id="home-library" aria-labelledby="home-library-title">
      <div className="section-heading">
        <div><p className="eyebrow">THƯ VIỆN HỌC TẬP</p><h2 id="home-library-title">Bộ đề</h2>
          <p className="section-lede">Chọn một đề để xem cấu trúc, nội dung và cách luyện phù hợp.</p></div>
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
