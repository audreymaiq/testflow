import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'

type HomeExam = {
  id: string; title: string; subtitle: string; icon: string; color: string; subject: string
  chapter_count: number; question_count: number; visibility: string; is_system_sample: boolean
}
type Page<T> = { count: number; next: string | null; results: T[] }

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

  function submit(event: FormEvent) {
    event.preventDefault()
    setSearch(input.trim())
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById('home-library')?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
  }

  return <div className="home-page">
    <section className="home-hero paper" aria-labelledby="home-title">
      <div>
        <p className="eyebrow">KHÔNG GIAN HỌC TẬP</p>
        <h1 id="home-title">Đề thi rõ ràng.<br />Tiến bộ thấy được.</h1>
        <p className="lede">Lưu đề, luyện tập và xem lại kết quả trong một nơi.</p>
        <a className="button primary" href="#home-library">Khám phá bộ đề</a>
      </div>
      <p className="home-hero-aside">Tạo đề của riêng bạn hoặc chọn một bộ đề đã được công khai để bắt đầu.</p>
    </section>
    <section className="home-library" id="home-library" aria-labelledby="home-library-title">
      <div className="section-heading">
        <div><p className="eyebrow">THƯ VIỆN</p><h2 id="home-library-title">Bộ đề</h2></div>
        <Link to="/library">Xem toàn bộ thư viện</Link>
      </div>
      <form className="home-search" role="search" onSubmit={submit}>
        <label htmlFor="home-query">Tìm bộ đề</label>
        <input id="home-query" type="search" value={input} onChange={(event) => setInput(event.target.value)}
          placeholder="Tên đề, môn học…" />
        <button className="button secondary" type="submit">Tìm kiếm</button>
      </form>
      {exams.isPending && <p role="status">Đang tải bộ đề…</p>}
      {exams.isError && <p role="alert">{exams.error.message} <button type="button" onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data?.count === 0 && <p>{search ? 'Không tìm thấy bộ đề phù hợp.' : 'Chưa có bộ đề nào. Hãy tạo đề đầu tiên trong thư viện.'}</p>}
      {exams.data && exams.data.count > 0 && <>
        <p className="result-count">{exams.data.count} bộ đề{search && ` cho “${search}”`}</p>
        <div className="home-deck-grid">
          {exams.data.results.map((exam) => <Link className="home-deck paper" key={exam.id} to={`/exams/${exam.id}`}>
            <DeckMark title={exam.title} icon={exam.icon} color={exam.color} />
            <span className="home-deck-copy">
              <strong>{exam.title} {exam.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</strong>
              {exam.subtitle && <small>{exam.subtitle}</small>}
              <span className="home-deck-meta">{exam.subject} · {exam.chapter_count} chương · {exam.question_count} câu</span>
            </span>
            <span className="home-deck-visibility">{exam.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</span>
          </Link>)}
        </div>
        {exams.data.next && <p><Link to="/library">Xem thêm trong thư viện</Link></p>}
      </>}
    </section>
  </div>
}
