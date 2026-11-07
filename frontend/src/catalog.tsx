import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal } from './shared'
import { DeckMark } from './exam-art'
import { TaxonomyEntry, TaxonomyNames } from './taxonomy'

type ExamSummary = {
  id: string; title: string; subtitle: string; level: string; grade: number | null
  icon: string; color: string
  subject: string; exam_type: string; visibility: string; question_count: number
  duration_minutes: number | null; has_answer_key: boolean; year: number | null
  is_system_sample: boolean
}
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

const levelNames: Record<string, string> = {
  TIEU_HOC: 'Tiểu học', THCS: 'THCS', THPT: 'THPT', DAI_HOC: 'Đại học', KHAC: 'Khác',
}

function FilterChips({ label, values, counts, selected, onChange }: {
  label: string; values: string[]; counts: Record<string, number>
  selected: string; onChange: (value: string) => void
}) {
  return <fieldset className="filter-chip-group"><legend>{label}</legend>
    <div className="filter-chip-list">
      <button type="button" aria-pressed={!selected} onClick={() => onChange('')}>Tất cả</button>
      {values.map((value) => <button type="button" key={value} aria-pressed={selected === value}
        onClick={() => onChange(selected === value ? '' : value)}>{value} <span className="mono">({counts[value] || 0})</span></button>)}
    </div>
  </fieldset>
}

export function LibraryPage() {
  const { user, api } = useAuth()
  const [filtersOpen, setFiltersOpen] = useState(() =>
    typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 901px)').matches)
  const [urlParams, setUrlParams] = useSearchParams()
  const query = urlParams.get('q') || ''
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
  const facets = useQuery({ queryKey: ['facets', user?.id], queryFn: () => api<Facets>('/facets/') })
  const params = new URLSearchParams(urlParams)
  params.set('page', String(page))
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
    ['exam_type', examType, `Loại: ${examType}`],
    ['has_answer_key', hasKey ? 'true' : '', 'Có đáp án'], ['mine', mine ? 'true' : '', 'Đề của tôi'],
  ].filter(([, value]) => value)

  return <section className="library-layout">
    <aside className={`library-filters paper${filtersOpen ? '' : ' is-collapsed'}`} aria-label="Bộ lọc đề">
      <div className="filter-heading"><p className="eyebrow">LỌC ĐỀ{activeFilters.length > 0 && ` · ${activeFilters.length} đang dùng`}</p>
        <div className="filter-heading-actions">
          {activeFilters.length > 0 && <button type="button" className="filter-reset" onClick={() => setUrlParams(new URLSearchParams(), { replace: true })}>Xóa bộ lọc</button>}
          <button type="button" className="filter-toggle" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((open) => !open)}>
            {filtersOpen ? 'Ẩn bộ lọc' : 'Hiện bộ lọc'}
          </button>
        </div></div>
      <label>Tìm kiếm<input type="search" value={query} onChange={(event) => updateFilter('q', event.target.value)} placeholder="Tên đề hoặc môn…" /></label>
      <label>Cấp học<select value={level} onChange={(event) => updateFilter('level', event.target.value, true)}>
        <option value="">Tất cả</option>
        {Object.entries(levelNames).map(([code, name]) => <option key={code} value={code}>{name} ({facets.data?.level_counts[code] || 0})</option>)}
      </select></label>
      <label>Lớp<select value={grade} onChange={(event) => updateFilter('grade', event.target.value)}>
        <option value="">Tất cả</option>{Array.from({ length: 12 }, (_, index) => index + 1).map((item) => <option key={item} value={item}>{item} ({facets.data?.grade_counts[item] || 0})</option>)}
      </select></label>
      <label>Môn học<select value={subject} onChange={(event) => updateFilter('subject', event.target.value)}>
        <option value="">Tất cả</option>{facets.data?.subjects.map(([code, name]) => <option key={code} value={code}>{name} ({facets.data?.subject_counts[code] || 0})</option>)}
      </select></label>
      <FilterChips label="Trường" values={facets.data?.schools || []} counts={facets.data?.school_counts || {}} selected={school}
        onChange={(value) => updateFilter('school', value)} />
      <FilterChips label="Ngành" values={facets.data?.majors || []} counts={facets.data?.major_counts || {}} selected={major}
        onChange={(value) => updateFilter('major', value)} />
      <label>Năm<input type="number" min={2000} max={2100} value={year} onChange={(event) => updateFilter('year', event.target.value)} /></label>
      <label>Loại đề<select value={examType} onChange={(event) => updateFilter('exam_type', event.target.value)}>
        <option value="">Tất cả</option>
        {Object.entries({ THI_CHINH_THUC: 'Thi chính thức', GIUA_KY: 'Giữa kỳ', CUOI_KY: 'Cuối kỳ', KIEM_TRA: 'Kiểm tra', ON_TAP: 'Ôn tập', OLYMPIC: 'Olympic', KHAC: 'Khác' }).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
      </select></label>
      <label className="check-label"><input type="checkbox" checked={hasKey} onChange={(event) => updateFilter('has_answer_key', event.target.checked ? 'true' : '')} /> Có đáp án</label>
      {user && <label className="check-label"><input type="checkbox" checked={mine} onChange={(event) => updateFilter('mine', event.target.checked ? 'true' : '')} /> Chỉ đề của tôi</label>}
      {facets.isError && <p role="alert">Không tải được các lựa chọn lọc. <button type="button" onClick={() => facets.refetch()}>Thử lại</button></p>}
    </aside>
    <div className="library-results paper">
      <div className="section-heading"><div><p className="eyebrow">THƯ VIỆN</p><h1>Đề thi</h1></div>
        {user && <Link className="button primary" to="/exams/new">Tạo đề</Link>}
      </div>
      <p className="section-lede">Tìm đề phù hợp, xem cấu trúc rồi chọn thi thử hoặc ôn tập.</p>
      {activeFilters.length > 0 && <div className="active-filters" aria-label="Bộ lọc đang áp dụng">
        {activeFilters.map(([key, , label]) => <button type="button" key={key}
          onClick={() => updateFilter(key, '', key === 'level')} aria-label={`Bỏ lọc ${label}`}>
          {label} <span aria-hidden="true">×</span></button>)}
      </div>}
      {exams.isPending && <p role="status">Đang tải danh sách…</p>}
      {exams.isError && <p role="alert">{exams.error.message} <button onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data && <>
        <p className="result-count">{exams.data.count} đề</p>
        {exams.data.count === 0 ? <div className="library-empty"><p>Chưa có đề phù hợp với bộ lọc.</p>
          {activeFilters.length > 0 && <button type="button" className="button secondary" onClick={() => setUrlParams(new URLSearchParams(), { replace: true })}>Xem tất cả đề</button>}</div> : <section className="exam-card-grid" aria-label="Danh sách đề">
          {exams.data.results.map((exam) => <Link className="exam-card" key={exam.id} to={`/exams/${exam.id}`}>
            <span className="exam-card-cover" aria-hidden="true">
              <svg viewBox="0 0 240 120" fill="none"><path d="M90 134c-17-68 25-121 93-128 33-3 65 8 84 30" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M113 132c-12-53 23-91 69-96 26-3 50 5 68 20" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 8"/>
                <circle cx="151" cy="80" r="8" stroke="currentColor" strokeWidth="2"/><circle cx="180" cy="76" r="8" fill="currentColor"/>
                <circle cx="209" cy="72" r="8" stroke="currentColor" strokeWidth="2"/><path d="m78 53 39-7m-42 21 24-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
              <span>{exam.subject}</span>
            </span>
            <span className="exam-card-body">
              <span className="exam-card-meta"><DeckMark title={exam.title} icon={exam.icon} color={exam.color} />
                <span>{levelNames[exam.level] || exam.level}{exam.grade ? ` · Lớp ${exam.grade}` : ''}</span>
                <span>{exam.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</span></span>
              <strong className="exam-card-title">{exam.title} {exam.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</strong>
              {exam.subtitle && <small>{exam.subtitle}</small>}
              <span className="exam-card-foot"><span className="mono">{exam.question_count} câu{exam.duration_minutes ? ` · ${exam.duration_minutes} phút` : ''}</span>
                <span>Xem đề <span aria-hidden="true">↗</span></span></span>
            </span>
          </Link>)}
        </section>}
        <nav className="pagination" aria-label="Phân trang đề thi">
          <button type="button" disabled={!exams.data.previous} onClick={() => updatePage(page - 1)}>Trang trước</button>
          <span>Trang {page}</span>
          <button type="button" disabled={!exams.data.next} onClick={() => updatePage(page + 1)}>Trang sau</button>
        </nav>
      </>}
    </div>
  </section>
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
    queryFn: () => api<{ questions: { id: string; text: string; choices: { label: string; text: string }[] }[] }>(`/exams/${id}/preview/`),
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
    <Link to="/library">← Thư viện</Link>
    <p className="eyebrow">{levelNames[exam.data.level]} / {exam.data.subject}</p>
    <h1>{exam.data.title} {exam.data.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</h1>
    {exam.data.subtitle && <p className="lede">{exam.data.subtitle}</p>}
    <dl className="exam-facts">
      <div><dt>Số câu</dt><dd>{exam.data.question_count}</dd></div>
      <div><dt>Thời gian</dt><dd>{exam.data.duration_minutes ? `${exam.data.duration_minutes} phút` : 'Không giới hạn'}</dd></div>
      <div><dt>Hiển thị</dt><dd>{exam.data.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</dd></div>
      <div><dt>Đáp án</dt><dd>{exam.data.has_answer_key ? 'Có' : 'Chưa đủ'}</dd></div>
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
        <button className="button primary" type="button" disabled={starting || !exam.data.has_answer_key} onClick={() => start('TIMED')}>Làm bài có giờ</button>
        <button className="button secondary" type="button" disabled={starting || !exam.data.has_answer_key || noChaptersSelected} onClick={() => start('PRACTICE')}>Luyện tập</button>
      </> : exam.data.has_answer_key ? <>
        <Link className="button primary" to="/login" state={{ from: `/exams/${id}`, practiceMode: 'TIMED' }}>Đăng nhập để làm bài có giờ</Link>
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
    <ul>{exam.data.sections.map((section) => <li key={section.id}>{section.title} · {section.kind}</li>)}</ul>
    <h2>Xem trước</h2>
    {preview.isPending && <p role="status">Đang tải câu mẫu…</p>}
    {preview.isError && <p role="alert">{preview.error.message}</p>}
    {preview.data?.questions.map((question, index) => <article className="preview-question" key={question.id}>
      <h3>Câu {index + 1}</h3><p>{question.text}</p>
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

type EditableQuestion = { text: string; choices: string[]; correct: string }
const blankQuestion = (): EditableQuestion => ({ text: '', choices: ['', '', '', ''], correct: 'A' })

export function ManualExamPage() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const subjects = useQuery({ queryKey: ['subjects'], queryFn: () => api<Subject[]>('/subjects/') })
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('toan')
  const [subjectName, setSubjectName] = useState('')
  const [schools, setSchools] = useState<string[]>([])
  const [majors, setMajors] = useState<string[]>([])
  const [level, setLevel] = useState('THPT')
  const [grade, setGrade] = useState(12)
  const [duration, setDuration] = useState(30)
  const [questions, setQuestions] = useState<EditableQuestion[]>([blankQuestion()])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  function updateQuestion(index: number, update: Partial<EditableQuestion>) {
    setQuestions((current) => current.map((question, position) => position === index ? { ...question, ...update } : question))
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setPending(true)
    const draft = {
      schema_version: 1,
      metadata: {
        title, level, grade: ['THPT', 'THCS', 'TIEU_HOC'].includes(level) ? grade : null,
        subject: subjectName.trim() || subject, schools, majors, exam_type: 'ON_TAP', scoring_preset: 'UNIFORM_10',
        max_score: 10, duration_minutes: duration, source: 'Tự biên soạn',
      },
      chapters: [],
      sections: [{ order: 1, title: 'Câu hỏi trắc nghiệm', kind: 'MCQ',
        scoring: { type: 'per_question', points: 1 }, passages: [],
        questions: questions.map((question, index) => ({
          tmp_id: `q${index + 1}`, order: index + 1, number_label: `Câu ${index + 1}`,
          kind: 'MCQ', text: question.text, provenance: { kind: 'manual' },
          choices: question.choices.map((text, choiceIndex) => ({
            label: 'ABCD'[choiceIndex], text, is_correct: question.correct === 'ABCD'[choiceIndex],
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
      <label>Tên đề<input required maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="form-grid">
        <label>Môn học<select value={subject} onChange={(event) => { setSubject(event.target.value); setSubjectName('') }}>
          {subjects.data?.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
        </select></label>
        <label>Cấp học<select value={level} onChange={(event) => { setLevel(event.target.value); setGrade(event.target.value === 'THPT' ? 12 : event.target.value === 'THCS' ? 9 : 5) }}>
          {Object.entries(levelNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select></label>
        {['THPT', 'THCS', 'TIEU_HOC'].includes(level) && <label>Lớp<input type="number" min={level === 'THPT' ? 10 : level === 'THCS' ? 6 : 1} max={level === 'THPT' ? 12 : level === 'THCS' ? 9 : 5} value={grade} onChange={(event) => setGrade(Number(event.target.value))} /></label>}
        <label>Thời gian (phút)<input type="number" min={1} max={300} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
      </div>
      <TaxonomyEntry kind="SUBJECT" label="Tên môn khác" value={subjectName} onChange={setSubjectName} />
      <p>Chọn tên đã có hoặc tự tạo tên mới để đề xuất hiện đúng trong bộ lọc thư viện.</p>
      <TaxonomyNames kind="SCHOOL" label="Trường" values={schools} onChange={setSchools} />
      <TaxonomyNames kind="MAJOR" label="Ngành" values={majors} onChange={setMajors} />
      <h2>Câu hỏi</h2>
      {questions.map((question, index) => <fieldset className="question-editor" key={index}>
        <legend>Câu {index + 1}</legend>
        <label>Nội dung<textarea required value={question.text} onChange={(event) => updateQuestion(index, { text: event.target.value })} /></label>
        {question.choices.map((choice, choiceIndex) => <label key={choiceIndex}>Đáp án {'ABCD'[choiceIndex]}
          <input required value={choice} onChange={(event) => {
            const choices = [...question.choices]; choices[choiceIndex] = event.target.value
            updateQuestion(index, { choices })
          }} />
        </label>)}
        <label>Đáp án đúng<select value={question.correct} onChange={(event) => updateQuestion(index, { correct: event.target.value })}>
          {'ABCD'.split('').map((label) => <option key={label} value={label}>{label}</option>)}
        </select></label>
        {questions.length > 1 && <button type="button" onClick={() => setQuestions((current) => current.filter((_, position) => position !== index))}>Xóa câu</button>}
      </fieldset>)}
      <button type="button" className="button secondary" onClick={() => setQuestions((current) => [...current, blankQuestion()])}>Thêm câu hỏi</button>
      {subjects.isError && <p role="alert">Không tải được danh sách môn học.</p>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={pending || subjects.isPending}>{pending ? 'Đang tạo…' : 'Tạo đề riêng tư'}</button>
    </form>
  </section>
}
