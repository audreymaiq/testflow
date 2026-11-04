import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './auth'

type ExamSummary = {
  id: string; title: string; subtitle: string; level: string; grade: number | null
  subject: string; exam_type: string; visibility: string; question_count: number
  duration_minutes: number | null; has_answer_key: boolean
}
type ExamDetail = ExamSummary & {
  chapters: { id: number; name: string; code: string }[]
  sections: { id: number; title: string; kind: string }[]
  source: string
}
type Subject = { code: string; name: string; levels: string[]; has_formula: boolean }
type Page<T> = { count: number; results: T[] }

const levelNames: Record<string, string> = {
  TIEU_HOC: 'Tiểu học', THCS: 'THCS', THPT: 'THPT', DAI_HOC: 'Đại học', KHAC: 'Khác',
}

export function LibraryPage() {
  const { user, api } = useAuth()
  const [query, setQuery] = useState('')
  const [mine, setMine] = useState(false)
  const [level, setLevel] = useState('')
  const params = new URLSearchParams()
  if (query.trim()) params.set('q', query.trim())
  if (mine) params.set('mine', 'true')
  if (level) params.set('level', level)
  const exams = useQuery({
    queryKey: ['exams', user?.id, query, mine, level],
    queryFn: () => api<Page<ExamSummary>>(`/exams/?${params.toString()}`),
  })

  return <section className="library-layout">
    <aside className="library-filters paper">
      <p className="eyebrow">LỌC ĐỀ</p>
      <label>Tìm kiếm<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên đề hoặc môn…" /></label>
      <label>Cấp học<select value={level} onChange={(event) => setLevel(event.target.value)}>
        <option value="">Tất cả</option>
        {Object.entries(levelNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
      </select></label>
      {user && <label className="check-label"><input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} /> Chỉ đề của tôi</label>}
    </aside>
    <div className="library-results paper">
      <div className="section-heading"><div><p className="eyebrow">THƯ VIỆN</p><h1>Đề thi</h1></div>
        {user && <Link className="button primary" to="/exams/new">Tạo đề</Link>}
      </div>
      {exams.isPending && <p role="status">Đang tải danh sách…</p>}
      {exams.isError && <p role="alert">{exams.error.message} <button onClick={() => exams.refetch()}>Thử lại</button></p>}
      {exams.data && <>
        <p className="result-count">{exams.data.count} đề</p>
        {exams.data.count === 0 ? <p>Chưa có đề phù hợp với bộ lọc.</p> : <div className="exam-table" role="table" aria-label="Danh sách đề">
          <div className="exam-row table-head" role="row"><span>TÊN ĐỀ</span><span>MÔN</span><span>SỐ CÂU</span><span>HIỂN THỊ</span></div>
          {exams.data.results.map((exam) => <Link className="exam-row" role="row" key={exam.id} to={`/exams/${exam.id}`}>
            <span className="exam-name"><strong>{exam.title}</strong><small>{exam.subtitle || levelNames[exam.level]}</small></span>
            <span>{exam.subject}</span><span className="mono">{exam.question_count}</span>
            <span>{exam.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</span>
          </Link>)}
        </div>}
      </>}
    </div>
  </section>
}

export function ExamDetailPage() {
  const { id } = useParams()
  const { user, api } = useAuth()
  const navigate = useNavigate()
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  const exam = useQuery({
    queryKey: ['exam', id, user?.id],
    queryFn: () => api<ExamDetail>(`/exams/${id}/`),
  })
  const preview = useQuery({
    queryKey: ['exam-preview', id, user?.id],
    queryFn: () => api<{ questions: { id: string; text: string; choices: { label: string; text: string }[] }[] }>(`/exams/${id}/preview/`),
    enabled: !!exam.data,
  })
  async function start(mode: 'TIMED' | 'PRACTICE') {
    setStarting(true); setStartError('')
    try {
      const session = await api<{ id: string }>('/practice/sessions/', {
        method: 'POST', body: JSON.stringify({ exam_id: id, mode }),
      })
      navigate(`/practice/${session.id}`)
    } catch (cause) { setStartError(cause instanceof Error ? cause.message : 'Không bắt đầu được bài làm.') }
    finally { setStarting(false) }
  }
  if (exam.isPending) return <p role="status">Đang tải đề…</p>
  if (exam.isError) return <section className="paper detail-panel"><h1>Không thể mở đề</h1><p role="alert">{exam.error.message}</p><Link to="/library">Về thư viện</Link></section>
  return <section className="paper detail-panel">
    <Link to="/library">← Thư viện</Link>
    <p className="eyebrow">{levelNames[exam.data.level]} / {exam.data.subject}</p>
    <h1>{exam.data.title}</h1>
    {exam.data.subtitle && <p className="lede">{exam.data.subtitle}</p>}
    <dl className="exam-facts">
      <div><dt>Số câu</dt><dd>{exam.data.question_count}</dd></div>
      <div><dt>Thời gian</dt><dd>{exam.data.duration_minutes ? `${exam.data.duration_minutes} phút` : 'Không giới hạn'}</dd></div>
      <div><dt>Hiển thị</dt><dd>{exam.data.visibility === 'PRIVATE' ? 'Riêng tư' : 'Công khai'}</dd></div>
      <div><dt>Đáp án</dt><dd>{exam.data.has_answer_key ? 'Có' : 'Chưa đủ'}</dd></div>
    </dl>
    <div className="start-actions">
      {user ? <>
        <button className="button primary" type="button" disabled={starting || !exam.data.has_answer_key} onClick={() => start('TIMED')}>Làm bài có giờ</button>
        <button className="button secondary" type="button" disabled={starting || !exam.data.has_answer_key} onClick={() => start('PRACTICE')}>Luyện tập</button>
      </> : <Link className="button primary" to="/login" state={{ from: `/exams/${id}` }}>Đăng nhập để làm bài</Link>}
      {startError && <p role="alert" className="form-error">{startError}</p>}
    </div>
    <h2>Nội dung đề</h2>
    <ul>{exam.data.sections.map((section) => <li key={section.id}>{section.title} · {section.kind}</li>)}</ul>
    <h2>Xem trước</h2>
    {preview.isPending && <p role="status">Đang tải câu mẫu…</p>}
    {preview.isError && <p role="alert">{preview.error.message}</p>}
    {preview.data?.questions.map((question, index) => <article className="preview-question" key={question.id}>
      <h3>Câu {index + 1}</h3><p>{question.text}</p>
      <ol type="A">{question.choices.map((choice) => <li key={choice.label}>{choice.text}</li>)}</ol>
    </article>)}
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
        subject, exam_type: 'ON_TAP', scoring_preset: 'UNIFORM_10',
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
        <label>Môn học<select value={subject} onChange={(event) => setSubject(event.target.value)}>
          {subjects.data?.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
        </select></label>
        <label>Cấp học<select value={level} onChange={(event) => { setLevel(event.target.value); setGrade(event.target.value === 'THPT' ? 12 : event.target.value === 'THCS' ? 9 : 5) }}>
          {Object.entries(levelNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select></label>
        {['THPT', 'THCS', 'TIEU_HOC'].includes(level) && <label>Lớp<input type="number" min={level === 'THPT' ? 10 : level === 'THCS' ? 6 : 1} max={level === 'THPT' ? 12 : level === 'THCS' ? 9 : 5} value={grade} onChange={(event) => setGrade(Number(event.target.value))} /></label>}
        <label>Thời gian (phút)<input type="number" min={1} max={300} value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
      </div>
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
