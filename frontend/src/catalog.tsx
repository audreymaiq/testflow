import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal } from './shared'
import { AnswerSheetArt } from './exam-art'
import { ExamCard, examTypeNames, levelNames, type ExamCardData } from './exam-card'
import { TaxonomyEntry, TaxonomyNames } from './taxonomy'
import { PrivateImage } from './private-image'
import heroDashboard from './assets/hero-dashboard.webp'

type ExamSummary = ExamCardData & { has_answer_key: boolean; year: number | null }
type ExamDetail = ExamSummary & {
  is_owner: boolean
  schools: string[]
  majors: string[]
  chapters: { id: number; name: string; code: string }[]
  sections: { id: number; title: string; kind: string }[]
  section_stats: { id: number; title: string; count: number }[]
  chapter_stats: { id: number; name: string; count: number }[]
  source: string
}
type Subject = { code: string; name: string; levels: string[]; has_formula: boolean }
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }
type Facets = {
  subjects: [string, string][]; schools: string[]; majors: string[]; levels: string[]
  subject_counts: Record<string, number>; school_counts: Record<string, number>
  major_counts: Record<string, number>; level_counts: Record<string, number>
  grade_counts: Record<string, number>
}
const sortOptions = [
  { value: '-created_at', label: 'Mới nhất' },
  { value: '-attempt_count', label: 'Phổ biến' },
  { value: 'year', label: 'Theo năm' },
]

export function LibraryPage() {
  const { user, api } = useAuth()
  const [heroQuery, setHeroQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const sortRef = useRef<HTMLDetailsElement>(null)
  const [filtersOpen, setFiltersOpen] = useState(() =>
    typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 901px)').matches)
  const [urlParams, setUrlParams] = useSearchParams()
  const query = urlParams.get('q') || ''
  const ordering = urlParams.get('ordering') || '-created_at'
  const sortLabel = sortOptions.find((option) => option.value === ordering)?.label || sortOptions[0].label
  const mine = urlParams.get('mine') === 'true'
  const level = urlParams.get('level') || ''
  const grade = urlParams.get('grade') || ''
  const subject = urlParams.get('subject') || ''
  const school = urlParams.get('school') || ''
  const major = urlParams.get('major') || ''
  const year = urlParams.get('year') || ''
  const examType = urlParams.get('exam_type') || ''
  const hasKey = urlParams.get('has_answer_key') === 'true'
  const page = Math.max(1, Number.parseInt(urlParams.get('page') || '1', 10) || 1)
  useEffect(() => setHeroQuery(query), [query])
  useEffect(() => {
    const closeSort = (event: PointerEvent) => {
      if (sortRef.current && !sortRef.current.contains(event.target as Node)) sortRef.current.open = false
    }
    document.addEventListener('pointerdown', closeSort)
    return () => document.removeEventListener('pointerdown', closeSort)
  }, [])
  function updateFilter(key: string, value: string, clearGrade = false) {
    const next = new URLSearchParams(urlParams)
    if (value.trim()) next.set(key, value.trim())
    else next.delete(key)
    if (clearGrade) next.delete('grade')
    next.delete('page')
    setUrlParams(next, { replace: true })
  }
  function updatePage(nextPage: number) {
    const next = new URLSearchParams(urlParams)
    if (nextPage > 1) next.set('page', String(nextPage))
    else next.delete('page')
    setUrlParams(next)
  }
  function chooseSort(value: string) {
    updateFilter('ordering', value)
    if (sortRef.current) {
      sortRef.current.open = false
      sortRef.current.querySelector('summary')?.focus()
    }
  }
  const facets = useQuery({ queryKey: ['facets', user?.id], queryFn: () => api<Facets>('/facets/') })
  const params = new URLSearchParams(urlParams)
  params.set('page', String(page))
  params.set('page_size', '6')
  const search = params.toString()
  const exams = useQuery({
    queryKey: ['exams', user?.id, search],
    queryFn: () => api<Page<ExamSummary>>(`/exams/?${search}`),
  })
  const activeFilters = [
    ['q', query, `Tìm: ${query}`], ['level', level, levelNames[level] || level],
    ['grade', grade, `Lớp ${grade}`],
    ['subject', subject, facets.data?.subjects.find(([code]) => code === subject)?.[1] || subject],
    ['school', school, school], ['major', major, major], ['year', year, `Năm ${year}`],
    ['exam_type', examType, `Loại: ${examTypeNames[examType] || examType}`],
    ['has_answer_key', hasKey ? 'true' : '', 'Có đáp án'], ['mine', mine ? 'true' : '', 'Đề của tôi'],
  ].filter(([, value]) => value)

  return <div className="library-page">
    <section className="library-hero" aria-labelledby="library-hero-title">
      <img src={heroDashboard} alt="" />
      <div className="library-hero-content">
        <h1 id="library-hero-title">Khám phá kho đề phong phú</h1>
        <p>Đề thi, đề kiểm tra và đề ôn tập từ cấp 1 đến đại học do cộng đồng chia sẻ.</p>
        <form className="library-hero-search" role="search" onSubmit={(event: FormEvent) => { event.preventDefault(); updateFilter('q', heroQuery) }}>
          <label className="visually-hidden" htmlFor="library-hero-query">Tìm đề thi</label>
          <div className="home-search-box"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7" stroke="currentColor" strokeWidth="2" /><path d="m16 16 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg><input id="library-hero-query" type="search" value={heroQuery} onChange={(event) => setHeroQuery(event.target.value)} placeholder="Tìm đề thi, trường hoặc @username..." /><button type="submit">Tìm đề</button></div>
        </form>
      </div>
    </section>
    <section className="library-layout">
    <aside className={`library-filters paper${filtersOpen ? '' : ' is-collapsed'}`} aria-label="Bộ lọc đề">
      <div className="filter-heading"><h2><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6h16M7 12h10m-7 6h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>Bộ lọc</h2>
        <button type="button" className="filter-reset" onClick={() => setUrlParams(new URLSearchParams(), { replace: true })}><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 11a8 8 0 1 1 2.3 5.6M4 5v6h6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>Đặt lại</button>
        <button type="button" className="filter-toggle" aria-controls="library-filter-fields" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((open) => !open)}>{filtersOpen ? 'Ẩn bộ lọc' : 'Hiện bộ lọc'}</button>
      </div>
      <div className="filter-fields" id="library-filter-fields">
        <fieldset className="library-levels"><legend>Cấp học</legend><div>{Object.entries(levelNames).map(([code, name]) => <button type="button" key={code} className={level === code ? 'is-active' : ''} aria-pressed={level === code} onClick={() => updateFilter('level', level === code ? '' : code, true)}>{name}</button>)}</div></fieldset>
        <label>Môn học<select value={subject} onChange={(event) => updateFilter('subject', event.target.value)}><option value="">Tất cả môn học</option>{facets.data?.subjects.map(([code, name]) => <option key={code} value={code}>{name} ({facets.data?.subject_counts[code] || 0})</option>)}</select></label>
        <fieldset className="library-types"><legend>Loại đề</legend><div>{Object.entries({ THI_CHINH_THUC: 'Thi chính thức', GIUA_KY: 'Giữa kỳ', CUOI_KY: 'Cuối kỳ', KIEM_TRA: 'Kiểm tra', ON_TAP: 'Ôn tập', OLYMPIC: 'Olympic', KHAC: 'Khác' }).map(([code, name]) => <label key={code}><input type="radio" name="exam-type" checked={examType === code} onChange={() => updateFilter('exam_type', code)} />{name}</label>)}</div>{examType && <button type="button" onClick={() => updateFilter('exam_type', '')}>Bỏ chọn loại đề</button>}</fieldset>
        <div className="library-switches"><label className="check-label"><input type="checkbox" checked={hasKey} onChange={(event) => updateFilter('has_answer_key', event.target.checked ? 'true' : '')} /> Có đáp án</label>{user && <label className="check-label"><input type="checkbox" checked={mine} onChange={(event) => updateFilter('mine', event.target.checked ? 'true' : '')} /> Chỉ đề của tôi</label>}</div>
        <label>Trường<select value={school} onChange={(event) => updateFilter('school', event.target.value)}><option value="">Chọn trường...</option>{facets.data?.schools.map((name) => <option key={name} value={name}>{name} ({facets.data?.school_counts[name] || 0})</option>)}</select></label>
        <label>Ngành<select value={major} onChange={(event) => updateFilter('major', event.target.value)}><option value="">Chọn ngành...</option>{facets.data?.majors.map((name) => <option key={name} value={name}>{name} ({facets.data?.major_counts[name] || 0})</option>)}</select></label>
        <details className="library-extra-filters"><summary>Lọc thêm theo lớp, năm</summary><div><label>Lớp<select value={grade} onChange={(event) => updateFilter('grade', event.target.value)}><option value="">Tất cả</option>{Array.from({ length: 12 }, (_, index) => index + 1).map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label>Năm<input type="number" min={2000} max={2100} value={year} onChange={(event) => updateFilter('year', event.target.value)} /></label></div></details>
        <label className="filter-search">Tìm kiếm<input type="search" value={query} onChange={(event) => updateFilter('q', event.target.value)} placeholder="Tìm đề hoặc @username…" /></label>
        {facets.isError && <p role="alert">Không tải được các lựa chọn lọc. <button type="button" onClick={() => facets.refetch()}>Thử lại</button></p>}
      </div>
    </aside>
    <div className="library-results paper">
      <div className="library-results-heading"><div className="library-results-title"><svg viewBox="0 0 32 32" width="39" height="39" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M16 28c-4-3-8-4-13-3V6c5-1 9 0 13 3 4-3 8-4 13-3v19c-5-1-9 0-13 3ZM16 9v19" /></svg><h2>Thư viện đề</h2></div><div className="library-toolbar"><div className="library-view-mode" role="group" aria-label="Kiểu hiển thị"><button type="button" aria-label="Dạng lưới" aria-pressed={viewMode === 'grid'} onClick={() => setViewMode('grid')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg></button><button type="button" aria-label="Dạng danh sách" aria-pressed={viewMode === 'list'} onClick={() => setViewMode('list')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 5h2m4 0h10M4 12h2m4 0h10M4 19h2m4 0h10" /></svg></button></div><details className="library-sort" ref={sortRef} onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() } }}><summary aria-label={`Sắp xếp: ${sortLabel}`}><span>Sắp xếp:</span><strong>{sortLabel}</strong><svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m3 6 5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></summary><div className="library-sort-options" role="group" aria-label="Sắp xếp đề thi">{sortOptions.map((option) => <button type="button" key={option.value} aria-pressed={ordering === option.value} onClick={() => chooseSort(option.value)}><span aria-hidden="true">{ordering === option.value ? '✓' : ''}</span>{option.label}</button>)}</div></details></div></div>
      {activeFilters.length > 0 && <div className="active-filters" aria-label="Bộ lọc đang áp dụng">
        {activeFilters.map(([key, , label]) => <button type="button" key={key}
          onClick={() => updateFilter(key, '', key === 'level')} aria-label={`Bỏ lọc ${label}`}>
          {label} <span aria-hidden="true">×</span></button>)}
      </div>}
      {exams.isPending && <p role="status">Đang tải danh sách…</p>}
      {exams.isError && <p role="alert">{exams.error.message} <button onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data && <>
        <p className="result-count">Tìm thấy <strong>{exams.data.count.toLocaleString('vi-VN')}</strong> đề</p>
        {exams.data.count === 0 ? <div className="library-empty"><p>Chưa có đề phù hợp với bộ lọc.</p>
          {activeFilters.length > 0 && <button type="button" className="button secondary" onClick={() => setUrlParams(new URLSearchParams(), { replace: true })}>Xem tất cả đề</button>}</div> : <section className={`exam-card-grid${viewMode === 'list' ? ' is-list' : ''}`} aria-label="Danh sách đề">
          {exams.data.results.map((exam) => <ExamCard key={exam.id} exam={exam} />)}
        </section>}
        <nav className="pagination" aria-label="Phân trang đề thi">
          <button type="button" aria-label="Trang trước" disabled={!exams.data.previous} onClick={() => updatePage(page - 1)}>‹</button>
          {Array.from({ length: Math.min(5, Math.max(1, Math.ceil(exams.data.count / 6))) }, (_, index) => Math.max(1, Math.min(page - 2, Math.max(1, Math.ceil(exams.data.count / 6) - 4))) + index).map((number) => <button type="button" key={number} className={number === page ? 'pagination-current' : ''} aria-current={number === page ? 'page' : undefined} aria-label={`Trang ${number}`} onClick={() => updatePage(number)}>{number}</button>)}
          {Math.ceil(exams.data.count / 6) > 5 && <><span aria-hidden="true">…</span><button type="button" aria-label={`Trang ${Math.ceil(exams.data.count / 6)}`} onClick={() => updatePage(Math.ceil(exams.data.count / 6))}>{Math.ceil(exams.data.count / 6)}</button></>}
          <button type="button" aria-label="Trang sau" disabled={!exams.data.next} onClick={() => updatePage(page + 1)}>›</button>
        </nav>
      </>}
    </div>
    </section>
  </div>
}

export function ExamDetailPage() {
  const { id } = useParams()
  const { user, loading, api } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const resumedExamId = useRef<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  const [ownerBusy, setOwnerBusy] = useState(false)
  const [ownerMessage, setOwnerMessage] = useState('')
  const [confirmation, setConfirmation] = useState<'DELETE' | 'HIDE' | 'WITHDRAW' | null>(null)
  const closeConfirmation = useCallback(() => { if (!ownerBusy) setConfirmation(null) }, [ownerBusy])
  const [chapterIds, setChapterIds] = useState<string[] | null>(null)
  const [includeWrong, setIncludeWrong] = useState(false)
  const [onlyWrong, setOnlyWrong] = useState(false)
  const [shuffleQuestions, setShuffleQuestions] = useState(false)
  const [shuffleOptions, setShuffleOptions] = useState(false)
  const exam = useQuery({
    queryKey: ['exam', id, user?.id],
    queryFn: () => api<ExamDetail>(`/exams/${id}/`),
    enabled: !loading,
  })
  const preview = useQuery({
    queryKey: ['exam-preview', id, user?.id],
    queryFn: () => api<{ questions: { id: string; text: string; choices: { label: string; text: string }[]; assets: string[] }[] }>(`/exams/${id}/preview/`),
    enabled: !loading && !!exam.data,
  })
  const practiceSummary = useQuery({
    queryKey: ['practice-exam-summary', id, user?.id],
    queryFn: () => api<{ wrong_question_count: number; session_count: number }>(`/practice/exams/${id}/summary/`),
    enabled: !loading && !!user && !!exam.data,
  })
  const selectedChapterIds = chapterIds ?? exam.data?.chapters.map((chapter) => String(chapter.id)) ?? []
  const noChaptersSelected = !onlyWrong && !!exam.data?.chapters.length && selectedChapterIds.length === 0
  const start = useCallback(async (mode: 'TIMED' | 'PRACTICE') => {
    if (mode === 'PRACTICE' && noChaptersSelected) {
      setStartError('Chọn ít nhất một chương để luyện tập.')
      return
    }
    setStarting(true); setStartError('')
    try {
      const session = await api<{ id: string }>('/practice/sessions/', {
        method: 'POST', body: JSON.stringify({
          exam_id: id, mode,
          ...(mode === 'PRACTICE' ? {
            chapter_ids: onlyWrong ? [] : selectedChapterIds,
            include_wrong_bank: includeWrong,
            only_wrong_bank: onlyWrong,
            shuffle_questions: shuffleQuestions,
            shuffle_options: shuffleOptions,
          } : {}),
        }),
      })
      navigate(`/practice/${session.id}`)
    } catch (cause) { setStartError(cause instanceof Error ? cause.message : 'Không bắt đầu được bài làm.') }
    finally { setStarting(false) }
  }, [api, id, onlyWrong, noChaptersSelected, selectedChapterIds, includeWrong, shuffleQuestions, shuffleOptions, navigate])
  const resumePractice = (location.state as { resumePractice?: unknown } | null)?.resumePractice
  useEffect(() => {
    if (!user || !id || !exam.data || resumedExamId.current === id) return
    if (resumePractice !== 'TIMED' && resumePractice !== 'PRACTICE') return
    resumedExamId.current = id
    navigate(location.pathname, { replace: true, state: null })
    void start(resumePractice)
  }, [user, id, exam.data, resumePractice, navigate, location.pathname, start])
  async function changeVisibility(visibility: 'PRIVATE' | 'PUBLIC') {
    setOwnerBusy(true); setOwnerMessage('')
    try {
      const result = await api<{ request_id: number | null }>(`/exams/${id}/visibility/`, {
        method: 'POST', body: JSON.stringify({ visibility }),
      })
      await queryClient.invalidateQueries({ queryKey: ['exam', id] })
      await queryClient.invalidateQueries({ queryKey: ['exams'] })
      setOwnerMessage(visibility === 'PUBLIC' ? `Đã gửi yêu cầu công khai #${result.request_id}.` : 'Đề đã chuyển về riêng tư.')
    } catch (cause) { setOwnerMessage(cause instanceof Error ? cause.message : 'Không đổi được trạng thái đề.') }
    finally { setOwnerBusy(false); setConfirmation(null) }
  }
  async function removeExam() {
    setOwnerBusy(true); setOwnerMessage('')
    try {
      await api<void>(`/exams/${id}/`, { method: 'DELETE' })
      await queryClient.invalidateQueries({ queryKey: ['exams'] })
      navigate('/library')
    } catch (cause) { setOwnerMessage(cause instanceof Error ? cause.message : 'Không xóa được đề.') }
    finally { setOwnerBusy(false); setConfirmation(null) }
  }
  async function hide() {
    setOwnerBusy(true); setOwnerMessage('')
    try {
      await api(`/exams/${id}/hide/`, { method: 'POST' })
      await queryClient.invalidateQueries({ queryKey: ['exam', id] })
      await queryClient.invalidateQueries({ queryKey: ['exams'] })
      setOwnerMessage('Đề đã được ẩn.')
    } catch (cause) { setOwnerMessage(cause instanceof Error ? cause.message : 'Không ẩn được đề.') }
    finally { setOwnerBusy(false); setConfirmation(null) }
  }
  const confirmationCopy = {
    DELETE: { title: 'Xóa đề?', body: 'Đề sẽ bị xóa khỏi thư viện của bạn.', action: 'Xác nhận xóa' },
    HIDE: { title: 'Ẩn đề?', body: 'Đề sẽ bị ẩn khỏi mọi người dùng.', action: 'Xác nhận ẩn' },
    WITHDRAW: { title: 'Chuyển về riêng tư?', body: 'Đề sẽ không còn hiển thị cho người khác ngay sau khi xác nhận.', action: 'Xác nhận chuyển' },
  }
  if (exam.isPending) return <p role="status">Đang tải đề…</p>
  if (exam.isError) return <section className="paper detail-panel"><h1>Không thể mở đề</h1><p role="alert">{exam.error.message}</p><Link to="/library">Về thư viện</Link></section>
  return <section className="paper detail-panel">
    <header className="detail-cover" style={{ '--cover-accent': /^#[0-9a-fA-F]{6}$/.test(exam.data.color) ? exam.data.color : '#2547C4' } as CSSProperties}>
      <AnswerSheetArt />
      <Link to="/library">← Thư viện</Link>
      <p className="eyebrow">{levelNames[exam.data.level]} / {exam.data.subject}</p>
      <h1>{exam.data.title} {exam.data.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</h1>
      {exam.data.subtitle && <p>{exam.data.subtitle}</p>}
    </header>
    <dl className="exam-facts">
      <div><dt>Số câu</dt><dd>{exam.data.question_count}</dd></div>
      <div><dt>Thời gian</dt><dd>{exam.data.duration_minutes ? `${exam.data.duration_minutes} phút` : 'Không giới hạn'}</dd></div>
      <div><dt>Hiển thị</dt><dd>{exam.data.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</dd></div>
      <div><dt>Đáp án</dt><dd>{exam.data.has_answer_key ? 'Có' : 'Chưa đủ'}</dd></div>
      <div><dt>Người đăng</dt><dd title={exam.data.owner_username || 'Ẩn danh'}>{exam.data.owner_username ? `@${exam.data.owner_username}` : 'Ẩn danh'}</dd></div>
      {exam.data.schools.length > 0 && <div><dt>Trường</dt><dd>{exam.data.schools.join(', ')}</dd></div>}
      {exam.data.majors.length > 0 && <div><dt>Ngành</dt><dd>{exam.data.majors.join(', ')}</dd></div>}
    </dl>
    <h2>Cấu trúc đề</h2>
    <ul>{exam.data.section_stats.map((item) => <li key={item.id}>{item.title}: {item.count} câu</li>)}</ul>
    {exam.data.chapter_stats.length > 0 && <ul>{exam.data.chapter_stats.map((item) => <li key={item.id}>{item.name}: {item.count} câu</li>)}</ul>}
    {user && <p>{practiceSummary.isPending ? 'Đang tải tiến độ…' : `${practiceSummary.data?.session_count || 0} lượt làm · ${practiceSummary.data?.wrong_question_count || 0} câu trong ngân hàng câu sai`}</p>}
    {user && (practiceSummary.data?.wrong_question_count || 0) > 0 && <button
      type="button" className="urgent-review" onClick={() => setOnlyWrong(true)}>
      🔥 Cần ôn tập gấp · {practiceSummary.data?.wrong_question_count} câu
    </button>}
    {user && <fieldset className="practice-config"><legend>Cấu hình ôn tập</legend>
      {exam.data.chapters.length > 0 && <div><strong>Chương</strong>{exam.data.chapters.map((chapter) => <label key={chapter.id}>
        <input type="checkbox" checked={selectedChapterIds.includes(String(chapter.id))} disabled={onlyWrong}
          onChange={(event) => setChapterIds((current) => {
            const selected = current ?? exam.data.chapters.map((item) => String(item.id))
            return event.target.checked ? [...selected, String(chapter.id)] : selected.filter((item) => item !== String(chapter.id))
          })} /> {chapter.name}
      </label>)}</div>}
      <label><input type="checkbox" checked={includeWrong} disabled={onlyWrong} onChange={(event) => setIncludeWrong(event.target.checked)} /> Bao gồm câu sai của tôi</label>
      <label><input type="checkbox" checked={onlyWrong} onChange={(event) => setOnlyWrong(event.target.checked)} /> Chỉ luyện câu sai</label>
      <label><input type="checkbox" checked={shuffleQuestions} onChange={(event) => setShuffleQuestions(event.target.checked)} /> Xáo thứ tự câu</label>
      <label><input type="checkbox" checked={shuffleOptions} onChange={(event) => setShuffleOptions(event.target.checked)} /> Xáo thứ tự đáp án</label>
      {noChaptersSelected && <p role="status">Chọn ít nhất một chương để luyện tập.</p>}
    </fieldset>}
    <div className="start-actions">
      {user ? <>
        <button className="button primary" type="button" disabled={starting || !exam.data.has_answer_key || !exam.data.duration_minutes} onClick={() => start('TIMED')}>Làm bài có giờ</button>
        {!exam.data.duration_minutes && <p className="field-hint">Đề không giới hạn thời gian chỉ dùng để luyện tập.</p>}
        <button className="button secondary" type="button" disabled={starting || !exam.data.has_answer_key || noChaptersSelected} onClick={() => start('PRACTICE')}>Luyện tập</button>
      </> : exam.data.has_answer_key ? <>
        {exam.data.duration_minutes && <Link className="button primary" to="/login" state={{ from: `/exams/${id}`, practiceMode: 'TIMED' }}>Đăng nhập để làm bài có giờ</Link>}
        <Link className="button secondary" to="/login" state={{ from: `/exams/${id}`, practiceMode: 'PRACTICE' }}>Đăng nhập để luyện tập</Link>
      </> : <p>Đề chưa đủ đáp án để bắt đầu làm bài.</p>}
      {startError && <p role="alert" className="form-error">{startError}</p>}
    </div>
    {exam.data.is_owner && <div className="owner-actions">
      <h2>Quản lý đề của tôi</h2>
      {exam.data.visibility === 'PRIVATE'
        ? <button type="button" className="button secondary" disabled={ownerBusy} onClick={() => changeVisibility('PUBLIC')}>Gửi duyệt công khai</button>
        : <button type="button" className="button secondary" disabled={ownerBusy} onClick={() => setConfirmation('WITHDRAW')}>Chuyển về riêng tư</button>}
      <button type="button" className="button secondary" disabled={ownerBusy} onClick={() => setConfirmation('DELETE')}>Xóa đề</button>
      {ownerMessage && <p role="status">{ownerMessage}</p>}
    </div>}
    {user?.roles.includes('Admin') && <div className="owner-actions"><button type="button" className="button secondary" disabled={ownerBusy} onClick={() => setConfirmation('HIDE')}>Ẩn đề với mọi người</button>{ownerMessage && !exam.data.is_owner && <p role="status">{ownerMessage}</p>}</div>}
    <h2>Nội dung đề</h2>
    <ul>{exam.data.sections.map((section) => <li key={section.id}>{section.title}</li>)}</ul>
    <h2>Xem trước</h2>
    {preview.isPending && <p role="status">Đang tải câu mẫu…</p>}
    {preview.isError && <p role="alert">{preview.error.message}</p>}
    {preview.data?.questions.map((question, index) => <article className="preview-question" key={question.id}>
      <h3>Câu {index + 1}</h3><p>{question.text}</p>
      {question.assets.map((assetId, assetIndex) => <PrivateImage key={assetId} path={`/exams/${id}/assets/${assetId}/`} alt={`Hình minh họa ${assetIndex + 1} của câu ${index + 1}`} className="question-asset" />)}
      <ol type="A">{question.choices.map((choice) => <li key={choice.label}>{choice.text}</li>)}</ol>
    </article>)}
    {confirmation && <Modal title={confirmationCopy[confirmation].title} onClose={closeConfirmation}>
      <p>{confirmationCopy[confirmation].body}</p>
      <button type="button" className="button primary" disabled={ownerBusy}
        onClick={() => { void (confirmation === 'DELETE' ? removeExam() : confirmation === 'HIDE' ? hide() : changeVisibility('PRIVATE')) }}>
        {ownerBusy ? 'Đang xử lý…' : confirmationCopy[confirmation].action}
      </button>
    </Modal>}
  </section>
}

type EditableQuestion = { kind: 'MCQ' | 'MCQ_MULTI'; text: string; choices: string[]; correct: string[] }
const blankQuestion = (): EditableQuestion => ({ kind: 'MCQ', text: '', choices: ['', '', '', ''], correct: ['A'] })

export function ManualExamPage() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const subjects = useQuery({ queryKey: ['subjects'], queryFn: () => api<Subject[]>('/subjects/') })
  const [title, setTitle] = useState('')
  const [subjectName, setSubjectName] = useState('Toán')
  const [schools, setSchools] = useState<string[]>([])
  const [majors, setMajors] = useState<string[]>([])
  const [level, setLevel] = useState('THPT')
  const [grade, setGrade] = useState(12)
  const [examType, setExamType] = useState('ON_TAP')
  const [duration, setDuration] = useState(30)
  const [unlimited, setUnlimited] = useState(false)
  const [questions, setQuestions] = useState<EditableQuestion[]>([blankQuestion()])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  function updateQuestion(index: number, update: Partial<EditableQuestion>) {
    setQuestions((current) => current.map((question, position) => position === index ? { ...question, ...update } : question))
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setError('')
    if (!title.trim() || !subjectName.trim()) {
      setError('Điền tên đề và môn học hợp lệ.')
      return
    }
    if (schools.length === 0) {
      setError('Chọn hoặc thêm ít nhất một trường.')
      return
    }
    if (questions.some((question) => question.correct.length === 0)) {
      setError('Mỗi câu hỏi cần ít nhất một đáp án đúng.')
      return
    }
    setPending(true)
    const draft = {
      schema_version: 1,
      metadata: {
        title: title.trim(), level, grade: ['THPT', 'THCS', 'TIEU_HOC'].includes(level) ? grade : null,
        subject: subjectName.trim(), schools, majors, exam_type: examType, scoring_preset: 'UNIFORM_10',
        max_score: 10, duration_minutes: unlimited ? null : duration, source: 'Tự biên soạn',
      },
      chapters: [],
      sections: [{ order: 1, title: 'Câu hỏi trắc nghiệm', kind: questions.some((question) => question.kind === 'MCQ_MULTI') ? 'MIXED' : 'MCQ',
        scoring: { type: 'per_question', points: 1 }, passages: [],
        questions: questions.map((question, index) => ({
          tmp_id: `q${index + 1}`, order: index + 1, number_label: `Câu ${index + 1}`,
          kind: question.kind, text: question.text, provenance: { kind: 'manual' },
          choices: question.choices.map((text, choiceIndex) => ({
            label: 'ABCD'[choiceIndex], text, is_correct: question.correct.includes('ABCD'[choiceIndex]),
          })),
        })),
      }],
    }
    try {
      const created = await api<{ id: string }>('/exams/manual/', {
        method: 'POST', body: JSON.stringify({ draft }),
      })
      await queryClient.invalidateQueries({ queryKey: ['exams'] })
      navigate(`/exams/${created.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể tạo đề.')
    } finally { setPending(false) }
  }

  return <section className="paper manual-panel">
    <p className="eyebrow">THƯ VIỆN / ĐỀ MỚI</p><h1>Tạo đề thủ công</h1>
    <p className="lede">Đề mới chỉ hiển thị cho bạn. Nội dung được lưu khi bạn chọn Tạo đề.</p>
    <form onSubmit={submit} className="manual-form">
      <label><span>Tên đề<span className="required-mark" aria-hidden="true"> *</span></span><input required maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="form-grid">
        <TaxonomyEntry kind="SUBJECT" label="Môn học" required suggestions={subjects.data?.map((item) => item.name) || []} value={subjectName} onChange={setSubjectName} />
        <label><span>Cấp học<span className="required-mark" aria-hidden="true"> *</span></span><select required value={level} onChange={(event) => { setLevel(event.target.value); setGrade(event.target.value === 'THPT' ? 12 : event.target.value === 'THCS' ? 9 : 5) }}>
          {Object.entries(levelNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select></label>
        {['THPT', 'THCS', 'TIEU_HOC'].includes(level) && <label><span>Lớp<span className="required-mark" aria-hidden="true"> *</span></span><input required type="number" min={level === 'THPT' ? 10 : level === 'THCS' ? 6 : 1} max={level === 'THPT' ? 12 : level === 'THCS' ? 9 : 5} value={grade} onChange={(event) => setGrade(Number(event.target.value))} /></label>}
        <label><span>Loại đề<span className="required-mark" aria-hidden="true"> *</span></span><select required value={examType} onChange={(event) => setExamType(event.target.value)}><option value="ON_TAP">Ôn tập</option><option value="KIEM_TRA">Kiểm tra</option><option value="GIUA_KY">Giữa kỳ</option><option value="CUOI_KY">Cuối kỳ</option><option value="THI_CHINH_THUC">Thi chính thức</option><option value="OLYMPIC">Olympic</option><option value="KHAC">Khác</option></select></label>
        <label><span>Thời gian (phút){!unlimited && <span className="required-mark" aria-hidden="true"> *</span>}</span><input required={!unlimited} disabled={unlimited} type="number" min={1} max={300} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
      </div>
      <label className="check-label"><input type="checkbox" checked={unlimited} onChange={(event) => setUnlimited(event.target.checked)} /> Không giới hạn thời gian (chỉ luyện tập)</label>
      <p>Chọn môn được gợi ý hoặc nhập tên môn mới. Nếu chưa có tên phù hợp, dùng Kiểm tra tên để tạo tên chuẩn.</p>
      <TaxonomyNames kind="SCHOOL" label="Trường" values={schools} onChange={setSchools} required />
      <TaxonomyNames kind="MAJOR" label="Ngành" values={majors} onChange={setMajors} />
      <h2>Câu hỏi</h2>
      {questions.map((question, index) => <fieldset className="question-editor" key={index}>
        <legend>Câu {index + 1}</legend>
        <label>Kiểu câu hỏi<select value={question.kind} onChange={(event) => updateQuestion(index, { kind: event.target.value as EditableQuestion['kind'], correct: question.correct.slice(0, 1) })}><option value="MCQ">Một đáp án đúng</option><option value="MCQ_MULTI">Nhiều đáp án đúng</option></select></label>
        <label>Nội dung<textarea required value={question.text} onChange={(event) => updateQuestion(index, { text: event.target.value })} /></label>
        {question.choices.map((choice, choiceIndex) => <label key={choiceIndex}>Đáp án {'ABCD'[choiceIndex]}
          <input required value={choice} onChange={(event) => {
            const choices = [...question.choices]; choices[choiceIndex] = event.target.value
            updateQuestion(index, { choices })
          }} />
        </label>)}
        {question.kind === 'MCQ' ? <label>Đáp án đúng<select aria-label="Đáp án đúng" value={question.correct[0]} onChange={(event) => updateQuestion(index, { correct: [event.target.value] })}>
          {'ABCD'.split('').map((label) => <option key={label} value={label}>{label}</option>)}
        </select></label> : <fieldset className="multi-answer-key"><legend>Đáp án đúng (chọn ít nhất một)</legend>{'ABCD'.split('').map((label) => <label key={label}><input type="checkbox" checked={question.correct.includes(label)} onChange={(event) => updateQuestion(index, { correct: event.target.checked ? [...question.correct, label] : question.correct.filter((item) => item !== label) })} /> {label}</label>)}</fieldset>}
        {questions.length > 1 && <button type="button" onClick={() => setQuestions((current) => current.filter((_, position) => position !== index))}>Xóa câu</button>}
      </fieldset>)}
      <button type="button" className="button secondary" onClick={() => setQuestions((current) => [...current, blankQuestion()])}>Thêm câu hỏi</button>
      {subjects.isError && <p role="alert">Không tải được danh sách môn học.</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={pending || subjects.isPending}>{pending ? 'Đang tạo…' : 'Tạo đề riêng tư'}</button>
    </form>
  </section>
}
