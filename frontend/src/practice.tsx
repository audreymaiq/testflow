import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useBeforeUnload, useBlocker, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal } from './shared'

type Choice = { label: string; text: string }
type Question = {
  id: string; number_label: string; kind: string; text: string; passage: string | null
  choices: Choice[]; statements: Choice[]; feedback?: Feedback
}
type Feedback = { status: string; earned: string; max_points: string; correct_answer: Record<string, unknown>; explanation: string }
type Answer = { question_id: string; value: Record<string, unknown>; flagged: boolean }
type Session = {
  id: string; exam_id: string; mode: 'TIMED' | 'PRACTICE'; status: string
  deadline_at: string | null; server_time: string
  sections: { id: string; questions: Question[] }[]; answers: Answer[]
}
type Result = {
  session_id: string; exam_id: string; mode: string; status: string
  total_score: string | null; max_score: string | null; correct_percent: string
  counts: Record<string, number>
  questions: (Feedback & { question_id: string; value: Record<string, unknown> })[]
}
type HistoryItem = {
  id: string; exam_id: string; exam_title: string; mode: string; status: string
  started_at: string; submitted_at: string | null; total_score: string | null; max_score: string | null
}
type HistoryPageData = { count: number; next: string | null; previous: string | null; results: HistoryItem[] }
type PersonalStats = { total_sessions: number; completed_sessions: number; timed_sessions: number; practice_sessions: number }

const statusName: Record<string, string> = {
  CORRECT: 'Đúng', PARTIAL: 'Đúng một phần', WRONG: 'Sai', BLANK: 'Chưa trả lời',
  SKIPPED: 'Đã bỏ qua', MANUAL: 'Chờ chấm thủ công',
}

function answerText(value: Record<string, unknown>) {
  if (typeof value.choice === 'string') return value.choice
  if (Array.isArray(value.choices)) return value.choices.join(', ')
  if (typeof value.value === 'boolean') return value.value ? 'Đúng' : 'Sai'
  if (typeof value.text === 'string') return value.text
  return Object.entries(value).map(([key, item]) => `${key}: ${item === true ? 'Đúng' : item === false ? 'Sai' : item}`).join('; ') || '—'
}

function hasAnswer(value: Record<string, unknown>) {
  return Object.values(value).some((item) =>
    typeof item === 'boolean' || (typeof item === 'string' && item.trim().length > 0)
    || (Array.isArray(item) && item.length > 0))
}

function QuestionInput({ question, value, onChange, disabled }: {
  question: Question; value: Record<string, unknown>
  onChange: (value: Record<string, unknown>) => void; disabled: boolean
}) {
  if (question.kind === 'MCQ' || question.kind === 'MCQ_MULTI') {
    const multi = question.kind === 'MCQ_MULTI'
    return <fieldset className="answer-options" disabled={disabled}>
      <legend>Chọn {multi ? 'các phương án' : 'một phương án'}</legend>
      {question.choices.map((choice) => {
        const selected = multi ? (Array.isArray(value.choices) && value.choices.includes(choice.label)) : value.choice === choice.label
        return <label key={choice.label} className={selected ? 'selected' : ''}>
          <input type={multi ? 'checkbox' : 'radio'} name={`answer-${question.id}`} checked={!!selected}
            onChange={() => {
              if (multi) {
                const current = Array.isArray(value.choices) ? value.choices as string[] : []
                onChange({ choices: selected ? current.filter((label) => label !== choice.label) : [...current, choice.label] })
              } else onChange({ choice: choice.label })
            }} />
          <strong>{choice.label}</strong><span>{choice.text}</span>
        </label>
      })}
    </fieldset>
  }
  if (question.kind === 'TRUE_FALSE') return <fieldset className="answer-options" disabled={disabled}>
    <legend>Chọn đúng hoặc sai</legend>
    {[true, false].map((choice) => <label key={String(choice)} className={value.value === choice ? 'selected' : ''}>
      <input type="radio" name={`answer-${question.id}`} checked={value.value === choice} onChange={() => onChange({ value: choice })} />
      {choice ? 'Đúng' : 'Sai'}
    </label>)}
  </fieldset>
  if (question.kind === 'TF_GROUP') return <fieldset className="answer-options" disabled={disabled}>
    <legend>Đúng hoặc sai cho từng ý</legend>
    {question.statements.map((item) => <div className="statement-row" key={item.label}>
      <span>{item.label}. {item.text}</span>
      {[true, false].map((choice) => <label key={String(choice)}>
        <input type="radio" name={`${question.id}-${item.label}`} checked={value[item.label] === choice}
          onChange={() => onChange({ ...value, [item.label]: choice })} />{choice ? 'Đúng' : 'Sai'}
      </label>)}
    </div>)}
  </fieldset>
  return <label className="text-answer">Câu trả lời
    {question.kind === 'ESSAY'
      ? <textarea value={String(value.text || '')} maxLength={10000} disabled={disabled}
          onChange={(event) => onChange({ text: event.target.value })} />
      : <input value={String(value.text || '')} maxLength={400} disabled={disabled}
          onChange={(event) => onChange({ text: event.target.value })} />}
  </label>
}

export function PracticePage() {
  const { sessionId } = useParams()
  const { api, user } = useAuth()
  const navigate = useNavigate()
  const [active, setActive] = useState(0)
  const [drafts, setDrafts] = useState<Record<string, Record<string, unknown>>>({})
  const [flagDrafts, setFlagDrafts] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [confirmSubmit, setConfirmSubmit] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const [serverOffset, setServerOffset] = useState(0)
  const allowNavigation = useRef(false)
  const session = useQuery({ queryKey: ['session', sessionId, user?.id], queryFn: () => api<Session>(`/practice/sessions/${sessionId}/`) })
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    session.data?.status === 'IN_PROGRESS' && !allowNavigation.current
    && currentLocation.pathname !== nextLocation.pathname)
  useBeforeUnload((event) => {
    if (session.data?.status === 'IN_PROGRESS') {
      event.preventDefault()
      event.returnValue = ''
    }
  })
  useEffect(() => { const id = window.setInterval(() => setTick(Date.now()), 1000); return () => window.clearInterval(id) }, [])
  useEffect(() => {
    if (session.data?.server_time) setServerOffset(new Date(session.data.server_time).getTime() - Date.now())
  }, [session.data?.server_time])
  const questions = useMemo(() => session.data?.sections.flatMap((section) => section.questions) || [], [session.data])
  const answeredIds = new Set(session.data?.answers.filter((answer) => hasAnswer(answer.value)).map((answer) => answer.question_id))
  Object.entries(drafts).forEach(([id, draft]) => {
    if (hasAnswer(draft)) answeredIds.add(id)
    else answeredIds.delete(id)
  })
  const correctCount = questions.filter((item) => item.feedback?.status === 'CORRECT').length
  const skippedCount = questions.filter((item) => item.feedback?.status === 'SKIPPED').length
  const question = questions[active]
  const saved = session.data?.answers.find((answer) => answer.question_id === question?.id)
  const value = question ? (drafts[question.id] || saved?.value || {}) : {}
  const closed = session.data?.status !== 'IN_PROGRESS'
  const remaining = session.data?.deadline_at ? Math.max(0, Math.ceil((new Date(session.data.deadline_at).getTime() - Date.now() - serverOffset) / 1000)) : null
  useEffect(() => {
    if (session.data?.status === 'IN_PROGRESS' && remaining === 0) {
      allowNavigation.current = true
      navigate(`/practice/${sessionId}/result`, { replace: true })
    }
  }, [remaining, session.data?.status, sessionId, navigate, tick])

  async function save(nextValue = value, target = question, flagOverride?: boolean) {
    if (!target || !session.data) return false
    setBusy(true); setError('')
    try {
      await api(`/practice/sessions/${sessionId}/answers/${target.id}/`, {
        method: 'PUT', body: JSON.stringify({
          value: nextValue, flagged: flagOverride ?? flagDrafts[target.id] ?? saved?.flagged ?? false,
        }),
      })
      await session.refetch()
      setDrafts((current) => {
        if (JSON.stringify(current[target.id]) !== JSON.stringify(nextValue)) return current
        const next = { ...current }; delete next[target.id]; return next
      })
      setFlagDrafts((current) => {
        if (current[target.id] !== (flagOverride ?? current[target.id])) return current
        const next = { ...current }; delete next[target.id]; return next
      })
      return true
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không lưu được câu trả lời.'); return false }
    finally { setBusy(false) }
  }

  useEffect(() => {
    if (!question || closed || session.data?.mode !== 'TIMED' || !drafts[question.id]) return
    const pendingValue = drafts[question.id]
    const timer = window.setTimeout(() => { void save(pendingValue, question) }, 650)
    return () => window.clearTimeout(timer)
  }, [drafts, question?.id, closed, session.data?.mode])

  function changeAnswer(next: Record<string, unknown>) {
    if (!question) return
    setDrafts((current) => ({ ...current, [question.id]: next }))
    if (session.data?.mode === 'PRACTICE' && (question.kind === 'MCQ' || question.kind === 'TRUE_FALSE')) {
      void save(next, question)
    }
  }

  async function goTo(index: number) {
    if (busy) return
    if (question && drafts[question.id] && !await save(drafts[question.id], question)) return
    setActive(index); setError('')
  }

  async function skip() {
    if (!question) return
    setBusy(true); setError('')
    try {
      await api(`/practice/sessions/${sessionId}/skip/${question.id}/`, { method: 'POST' })
      await session.refetch()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không bỏ qua được câu này.') }
    finally { setBusy(false) }
  }

  async function submit() {
    setConfirmSubmit(false)
    if (question && drafts[question.id] && !await save(drafts[question.id], question)) return
    setBusy(true); setError('')
    try {
      await api(`/practice/sessions/${sessionId}/submit/`, { method: 'POST' })
      allowNavigation.current = true
      navigate(`/practice/${sessionId}/result`, { replace: true })
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không nộp được bài.') }
    finally { setBusy(false) }
  }

  async function confirmLeave() {
    if (blocker.state !== 'blocked' || leaving || busy) return
    setLeaving(true)
    try {
      if (question && drafts[question.id] && !await save(drafts[question.id], question)) return
      blocker.proceed()
    } finally { setLeaving(false) }
  }

  if (session.isPending) return <p role="status">Đang tải bài làm…</p>
  if (session.isError) return <section className="paper practice-panel"><h1>Không mở được bài làm</h1><p role="alert">{session.error.message}</p></section>
  if (!question) return <section className="paper practice-panel"><h1>Bài làm không có câu hỏi</h1></section>
  return <section className="paper practice-panel">
    <div className="practice-header"><div><p className="eyebrow">{session.data.mode === 'TIMED' ? 'LÀM BÀI CÓ GIỜ' : 'LUYỆN TẬP'}</p>
      <h1>Bài làm của bạn</h1></div>
      {remaining !== null && <p className="timer" role="timer" aria-label="Thời gian còn lại">{Math.floor(remaining / 60).toString().padStart(2, '0')}:{(remaining % 60).toString().padStart(2, '0')}</p>}
    </div>
    <p className="practice-progress-label" aria-label="Tiến độ bài làm">Đã trả lời <strong>{answeredIds.size}/{questions.length}</strong> · {session.data.mode === 'PRACTICE'
      ? `${correctCount} đúng · ${skippedCount} bỏ qua` : 'Đúng: xem sau khi nộp'}</p>
    <div className="practice-progress-track" role="progressbar" aria-label="Số câu đã trả lời"
      aria-valuenow={answeredIds.size} aria-valuemin={0} aria-valuemax={questions.length}>
      <span style={{ width: `${questions.length ? answeredIds.size / questions.length * 100 : 0}%` }} />
    </div>
    <nav className="question-nav" aria-label="Chọn câu hỏi">{questions.map((item, index) =>
      <button type="button" key={item.id} onClick={() => { void goTo(index) }} disabled={busy}
        aria-current={index === active ? 'step' : undefined}
        aria-label={`Câu ${index + 1}${answeredIds.has(item.id) ? ', đã trả lời' : ''}${(flagDrafts[item.id] ?? session.data.answers.find((answer) => answer.question_id === item.id)?.flagged) ? ', đánh dấu xem lại' : ''}`}
        className={[answeredIds.has(item.id) ? 'answered' : '', (flagDrafts[item.id] ?? session.data.answers.find((answer) => answer.question_id === item.id)?.flagged) ? 'flagged' : ''].filter(Boolean).join(' ')}>{index + 1}</button>)}</nav>
    {closed && <p role="status">Bài làm đã kết thúc. <Link to={`/practice/${sessionId}/result`}>Xem kết quả</Link></p>}
    <article className="active-question"><p className="eyebrow">CÂU {active + 1} / {questions.length}</p>
      <h2>{question.number_label}</h2>{question.passage && <blockquote>{question.passage}</blockquote>}
      <p className="question-text">{question.text}</p>
      <QuestionInput question={question} value={value} disabled={closed || !!question.feedback || busy}
        onChange={changeAnswer} />
      {session.data.mode === 'TIMED' && !closed && <label className="flag-control">
        <input type="checkbox" checked={flagDrafts[question.id] ?? saved?.flagged ?? false} disabled={busy}
          onChange={(event) => {
            const flagged = event.target.checked
            setFlagDrafts((current) => ({ ...current, [question.id]: flagged }))
            void save(value, question, flagged)
          }} /> Đánh dấu để xem lại
      </label>}
      {question.feedback && <div className="feedback" role="status"><strong>{statusName[question.feedback.status] || question.feedback.status}</strong>
        <p>Đáp án: {answerText(question.feedback.correct_answer)}</p>
        {question.feedback.explanation && <p>{question.feedback.explanation}</p>}</div>}
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="practice-actions">
        {!closed && !question.feedback && <button type="button" className="button primary" onClick={() => { void save() }} disabled={busy || Object.keys(value).length === 0}>Lưu câu trả lời</button>}
        {!closed && session.data.mode === 'PRACTICE' && !question.feedback && <button type="button" className="button secondary" onClick={skip} disabled={busy}>Bỏ qua</button>}
        {active > 0 && <button type="button" className="button secondary" onClick={() => { void goTo(active - 1) }} disabled={busy}>Câu trước</button>}
        {active + 1 < questions.length && <button type="button" className="button secondary" onClick={() => { void goTo(active + 1) }} disabled={busy}>Câu tiếp</button>}
      </div>
    </article>
    {!closed && <div className="practice-actions">
      <button type="button" className="button submit-button" onClick={() => setConfirmSubmit(true)} disabled={busy}>Nộp bài</button>
      <button type="button" className="button secondary" onClick={() => navigate(`/exams/${session.data.exam_id}`)} disabled={busy}>Thoát bài làm</button>
    </div>}
    {blocker.state === 'blocked' && <Modal title="Thoát bài làm?" onClose={() => { if (!leaving) blocker.reset() }}>
      <p>Bài làm sẽ được giữ để bạn tiếp tục từ Lịch sử. Câu trả lời đang sửa sẽ được lưu trước khi thoát.</p>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="button" className="button primary" disabled={leaving || busy} onClick={() => { void confirmLeave() }}>
        {leaving ? 'Đang lưu…' : 'Lưu và thoát'}
      </button>
    </Modal>}
    {confirmSubmit && <Modal title="Nộp bài?" onClose={() => { if (!busy) setConfirmSubmit(false) }}>
      <p>Nộp bài và xem kết quả? Bạn sẽ không thể sửa câu trả lời sau khi nộp.</p>
      <button type="button" className="button primary" disabled={busy} onClick={() => { void submit() }}>
        {busy ? 'Đang nộp…' : 'Xác nhận nộp bài'}
      </button>
    </Modal>}
  </section>
}

export function ResultPage() {
  const { sessionId } = useParams()
  const { api, user } = useAuth()
  const result = useQuery({ queryKey: ['result', sessionId, user?.id], queryFn: () => api<Result>(`/practice/sessions/${sessionId}/result/`) })
  if (result.isPending) return <p role="status">Đang tải kết quả…</p>
  if (result.isError) return <section className="paper practice-panel"><h1>Chưa có kết quả</h1><p role="alert">{result.error.message}</p><Link to={`/practice/${sessionId}`}>Trở lại bài làm</Link></section>
  return <section className="paper practice-panel">
    <p className="eyebrow">KẾT QUẢ / {result.data.mode === 'TIMED' ? 'BÀI THI' : 'LUYỆN TẬP'}</p>
    <h1>Kết quả bài làm</h1>
    <div className="result-score"><div><span className="eyebrow">ĐIỂM BÀI LÀM</span><strong>{result.data.total_score === null ? 'Chưa tính điểm' : `${result.data.total_score} / ${result.data.max_score}`}</strong></div>
      <span className="result-percent"><strong>{result.data.correct_percent}%</strong> câu đúng</span></div>
    <div className="result-distribution" role="img" aria-label="Phân bố kết quả từng câu">
      {(['CORRECT', 'PARTIAL', 'WRONG', 'SKIPPED', 'BLANK', 'MANUAL'] as const).map((status) => {
        const count = result.data.counts[status] || 0
        return count > 0 ? <span key={status} className={`result-segment status-${status.toLowerCase()}`}
          style={{ width: `${count / Math.max(1, result.data.questions.length) * 100}%` }} title={`${count} ${statusName[status].toLowerCase()}`} /> : null
      })}
    </div>
    <ul className="result-legend">
      {(['CORRECT', 'PARTIAL', 'WRONG', 'SKIPPED', 'BLANK', 'MANUAL'] as const).map((status) => <li key={status} className={`status-${status.toLowerCase()}`}>
        <span aria-hidden="true" />{statusName[status]} <strong>{result.data.counts[status] || 0}</strong></li>)}
    </ul>
    <h2>Chi tiết từng câu</h2>
    {result.data.questions.map((item, index) => <article className="result-question" key={item.question_id}>
      <h3>Câu {index + 1} <span className={`result-status status-${item.status.toLowerCase()}`}>{statusName[item.status] || item.status}</span></h3>
      <p>Đã trả lời: {answerText(item.value)}</p>
      <p>Đáp án: {answerText(item.correct_answer)}</p>
      <p>Điểm: {item.earned} / {item.max_points}</p>
      {item.explanation && <p>Giải thích: {item.explanation}</p>}
    </article>)}
    <div className="practice-actions">
      <Link className="button primary" to={`/exams/${result.data.exam_id}`}
        state={{ resumePractice: result.data.mode }}>Làm lại</Link>
      <Link className="button secondary" to="/">Về trang chủ</Link>
      <Link to={`/exams/${result.data.exam_id}`}>Xem đề thi</Link>
    </div>
  </section>
}

export function HistoryPage() {
  const { api, user } = useAuth()
  const [page, setPage] = useState(1)
  const history = useQuery({ queryKey: ['practice-history', user?.id, page], queryFn: () => api<HistoryPageData>(`/practice/sessions/history/?page=${page}`) })
  const stats = useQuery({ queryKey: ['practice-stats', user?.id], queryFn: () => api<PersonalStats>('/practice/stats/') })
  return <section className="paper practice-panel">
    <p className="eyebrow">TIẾN ĐỘ CÁ NHÂN</p><h1>Lịch sử làm bài</h1>
    {stats.isPending && <p role="status">Đang tải thống kê…</p>}
    {stats.isError && <p role="alert">{stats.error.message}</p>}
    {stats.data && <dl className="history-stats">
      <div><dt>Lượt làm</dt><dd>{stats.data.total_sessions}</dd></div>
      <div><dt>Đã hoàn thành</dt><dd>{stats.data.completed_sessions}</dd></div>
      <div><dt>Thi có giờ</dt><dd>{stats.data.timed_sessions}</dd></div>
      <div><dt>Ôn tập</dt><dd>{stats.data.practice_sessions}</dd></div>
    </dl>}
    {history.isPending && <p role="status">Đang tải lịch sử…</p>}
    {history.isError && <p role="alert">{history.error.message} <button onClick={() => history.refetch()}>Thử lại</button></p>}
    {history.data?.count === 0 && <p>Bạn chưa có bài làm. <Link to="/library">Chọn một đề trong thư viện</Link>.</p>}
    {history.data?.results.map((item) => <article className="history-item" key={item.id}>
      <div><h2>{item.exam_title}</h2><p>{new Date(item.started_at).toLocaleString('vi-VN')} · {item.mode === 'TIMED' ? 'Thi có giờ' : 'Ôn tập'} · {item.status === 'IN_PROGRESS' ? 'Đang làm' : 'Đã nộp'}</p></div>
      <div><strong>{item.total_score === null ? '—' : `${item.total_score} / ${item.max_score}`}</strong>
        <Link to={item.status === 'IN_PROGRESS' ? `/practice/${item.id}` : `/practice/${item.id}/result`}>{item.status === 'IN_PROGRESS' ? 'Tiếp tục' : 'Xem kết quả'}</Link></div>
    </article>)}
    {history.data && <nav className="pagination" aria-label="Phân trang lịch sử">
      <button disabled={!history.data.previous} onClick={() => setPage(page - 1)}>Trang trước</button>
      <span>Trang {page}</span>
      <button disabled={!history.data.next} onClick={() => setPage(page + 1)}>Trang sau</button>
    </nav>}
  </section>
}
