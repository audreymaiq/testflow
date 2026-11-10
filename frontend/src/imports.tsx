import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal } from './shared'
import { PrivateImage } from './private-image'
import { TaxonomyEntry, TaxonomyNames } from './taxonomy'

type Issue = { line?: number; page_no?: number; code: string; message: string; severity: 'ERROR' | 'WARNING'; resolved_at?: string }
type DraftChoice = { label: string; text: string; is_correct: boolean }
type DraftQuestion = { tmp_id: string; order: number; kind: string; text: string; explanation: string; choices: DraftChoice[] }
type ImportDraft = { metadata: Record<string, unknown>; sections: { title: string; questions: DraftQuestion[] }[] }
type Job = {
  id: string
  status: string
  source_kind: 'TXT' | 'OCR'
  original_filename: string
  page_count: number | null
  error_code?: string
  pages?: { page_no: number; status: string; error_code?: string | null }[]
  exam_id: string | null
  discard_reason?: string
  report?: { valid: number; skipped: number; issues: Issue[] }
  draft_summary?: { title: string | null; questions: number; chapters: number }
  draft?: ImportDraft
}

const processingStatuses = new Set(['UPLOADED', 'INGESTING', 'EXTRACTING', 'ASSEMBLING'])
const statusLabels: Record<string, string> = {
  UPLOADED: 'Đã nhận tệp', INGESTING: 'Đang chuẩn bị trang', EXTRACTING: 'Đang nhận dạng trang',
  ASSEMBLING: 'Đang ghép bản nháp', NEEDS_REVIEW: 'Cần kiểm tra', APPROVED: 'Đã lưu đề',
  REJECTED: 'Đã bỏ bản nháp', FAILED: 'Xử lý thất bại',
}
const resolvableCodes = new Set([
  'E_ANSWER_CONFLICT', 'E_ANSWER_INVALID', 'E_ANSWER_UNMATCHED', 'E_ANSWER_UNSUPPORTED',
  'E_CONTINUATION_UNMATCHED', 'E_FIGURE_UNMATCHED', 'E_HEADER_CONFLICT', 'E_NO_QUESTIONS',
  'E_PASSAGE_UNANCHORED', 'E_PASSAGE_UNMATCHED', 'E_QUESTION_INVALID',
])

function ErrorText({ message }: { message: string }) {
  return message ? <p role="alert" className="form-error">{message}</p> : null
}

export function AddExamPage() {
  return <section className="paper manual-panel add-exam-panel">
    <p className="eyebrow">THƯ VIỆN / THÊM ĐỀ</p>
    <h1>Thêm đề</h1>
    <div className="add-exam-options">
      <Link to="/exams/new"><span className="add-exam-option-index">01</span><strong>Tạo đề mới</strong><span>Viết câu hỏi và đáp án trực tiếp.</span><span aria-hidden="true">↗</span></Link>
      <Link to="/imports/document/new"><span className="add-exam-option-index">02</span><strong>Thêm đề có sẵn</strong><span>Nhập PDF, DOCX hoặc ảnh; kiểm tra nội dung trước khi lưu.</span><span aria-hidden="true">↗</span></Link>
    </div>
  </section>
}

export function TxtImportPage() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [durationMode, setDurationMode] = useState<'FILE' | 'TIMED' | 'UNTIMED'>('FILE')
  const [durationMinutes, setDurationMinutes] = useState(30)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [showGuide, setShowGuide] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setPending(true); setError('')
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('duration_mode', durationMode)
      if (durationMode === 'TIMED') body.append('duration_minutes', String(durationMinutes))
      const job = await api<Job>('/imports/txt/', { method: 'POST', body })
      navigate(`/imports/${job.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể nhập tệp.')
    } finally { setPending(false) }
  }

  return <section className="paper manual-panel">
    <p className="eyebrow">THƯ VIỆN / THÊM ĐỀ CÓ SẴN</p>
    <h1>Thêm đề có sẵn</h1>
    <p className="lede">Chọn tệp TXT mã hóa UTF-8, tối đa 2 MB. Sau khi xác nhận tệp, bạn sẽ xem lại nội dung và thông tin đề trước khi lưu riêng tư.</p>
    <button className="text-button" type="button" onClick={() => setShowGuide(true)}>Xem hướng dẫn định dạng TXT</button>
    <form className="manual-form" onSubmit={submit}>
      <label>Chọn tệp .txt<input type="file" accept=".txt,text/plain" required onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
      <div className="form-grid">
        <label>Thời gian làm bài<select value={durationMode} onChange={(event) => setDurationMode(event.target.value as 'FILE' | 'TIMED' | 'UNTIMED')}>
          <option value="FILE">Theo tệp (nếu có)</option><option value="TIMED">Có giờ</option><option value="UNTIMED">Không giới hạn</option>
        </select></label>
        {durationMode === 'TIMED' && <label>Số phút<input type="number" min={1} max={300} required value={durationMinutes} onChange={(event) => setDurationMinutes(Number(event.target.value))} /></label>}
      </div>
      <ErrorText message={error} />
      <button className="button primary" type="submit" disabled={!file || pending}>{pending ? 'Đang phân tích…' : 'Xác nhận'}</button>
    </form>
    <p><Link to="/imports/document/new">Nhập PDF, DOCX hoặc ảnh</Link> · <Link to="/imports">Xem các tệp đã nhập</Link></p>
    {showGuide && <Modal title="Định dạng tệp TXT" onClose={() => setShowGuide(false)}>
      <p>Mỗi câu hỏi nằm trong một chương. Viết câu hỏi, các lựa chọn A–F, rồi một dòng đáp án bắt đầu bằng <code>=&gt;</code>. Ví dụ tương thích Quiz Rush v1:</p>
      <pre className="txt-format-example"><code>{`#TITLE: Ôn tập
[CH1] Số học
2 + 2 bằng bao nhiêu?
A. 3
B. 4
=>B`}</code></pre>
      <p>TXT v2 có thể thêm <code>#SUBJECT</code>, <code>#LEVEL</code>, <code>#GRADE</code>, <code>#TYPE</code>, <code>#DURATION</code> (số phút) và các trường khác ở đầu tệp. Các dạng đáp án thêm:</p>
      <ul>
        <li><code>=&gt;A,C</code>: chọn nhiều đáp án.</li>
        <li><code>=&gt;T</code> hoặc <code>=&gt;F</code>: đúng/sai, không có lựa chọn.</li>
        <li><code>=&gt;#3.5</code>: câu trả lời ngắn, không có lựa chọn.</li>
        <li><code>#EXPLAIN: …</code> ngay sau đáp án: lời giải.</li>
      </ul>
      <p>Có thể thêm <code>#TRUONG</code> và <code>#NGANH</code>; bạn sẽ kiểm tra tên chuẩn ở bước xem lại. Lưu tệp bằng UTF-8, tối đa 2 MB và 20.000 dòng. Hệ thống báo lỗi theo dòng và cho xem bản nháp trước khi lưu đề riêng tư.</p>
    </Modal>}
  </section>
}

export function ImportsPage() {
  const { api } = useAuth()
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    api<{ results: Job[] }>('/imports/mine/').then((value) => setJobs(value.results)).catch((cause) => setError(cause instanceof Error ? cause.message : 'Không tải được danh sách.'))
  }, [api])
  return <section className="paper library-panel">
    <p className="eyebrow">THƯ VIỆN / TỆP ĐÃ NHẬP</p><h1>Các lần nhập đề</h1>
    <Link className="button primary" to="/add-exam">Thêm đề</Link>
    <ErrorText message={error} />
    {jobs.length === 0 && !error && <p>Chưa có tệp nào.</p>}
    <ul>{jobs.map((job) => <li key={job.id}><Link to={`/imports/${job.id}`}>{job.original_filename}</Link> — {job.status} — {job.draft_summary?.questions || 0} câu</li>)}</ul>
  </section>
}

export function ImportReviewPage() {
  const { jobId } = useParams()
  const { api, apiBlob } = useAuth()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [editor, setEditor] = useState('')
  const [metadata, setMetadata] = useState<Record<string, unknown>>({})
  const [metadataDirty, setMetadataDirty] = useState(false)
  const [questionsDirty, setQuestionsDirty] = useState(false)
  const [selectedQuestion, setSelectedQuestion] = useState('')
  const [subjects, setSubjects] = useState<{ code: string; name: string }[]>([])
  const [editing, setEditing] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [discardReason, setDiscardReason] = useState('')
  const [selectedPage, setSelectedPage] = useState(1)
  const [resolutionReasons, setResolutionReasons] = useState<Record<number, string>>({})
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    if (!jobId) return
    let active = true
    let initializedDraft = false
    let inFlight = false
    let timer: number | undefined
    async function load() {
      if (inFlight) return
      inFlight = true
      try {
        const value = await api<Job>(`/imports/${jobId}/`)
        if (!active) return
        setJob(value)
        setError('')
        if (value.draft && !initializedDraft) {
          initializedDraft = true
          setEditor(JSON.stringify(value.draft, null, 2))
          setMetadata(value.draft.metadata || {})
          setMetadataDirty(false)
          setQuestionsDirty(false)
          setSelectedQuestion(value.draft.sections.flatMap((section) => section.questions)[0]?.tmp_id || '')
        }
        if (['NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'FAILED'].includes(value.status) && timer !== undefined) window.clearInterval(timer)
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : 'Không tải được lần nhập đề.')
      } finally { inFlight = false }
    }
    void load()
    timer = window.setInterval(() => { void load() }, 2500)
    return () => { active = false; window.clearInterval(timer) }
  }, [jobId, retryVersion])

  useEffect(() => {
    api<{ code: string; name: string }[]>('/subjects/').then(setSubjects).catch(() => setSubjects([]))
  }, [])

  async function replace(data: unknown) {
    if (!jobId) return
    setPending(true); setError(''); setMessage('')
    try {
      const value = await api<Job>(`/imports/${jobId}/`, { method: 'PATCH', body: JSON.stringify({ draft: data }) })
      setJob(value); setEditor(JSON.stringify(value.draft, null, 2))
      setMetadata((value.draft?.metadata || {}) as Record<string, unknown>)
      setMetadataDirty(false)
      setQuestionsDirty(false)
      setEditing(false); setMessage('Đã lưu bản nháp.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không lưu được bản nháp.') }
    finally { setPending(false) }
  }

  function field(name: string, value: string | number | null) {
    setMetadata((current) => ({ ...current, [name]: value }))
    setMetadataDirty(true)
  }

  function fieldList(name: 'schools' | 'majors', values: string[]) {
    setMetadata((current) => ({ ...current, [name]: values }))
    setMetadataDirty(true)
  }

  async function saveMetadata(event: FormEvent) {
    event.preventDefault()
    if (!job?.draft) return
    if (!String(metadata.title || '').trim() || !String(metadata.subject || '').trim()) {
      setError('Điền tên đề và môn học hợp lệ.')
      return
    }
    if (!Array.isArray(metadata.schools) || metadata.schools.length === 0) {
      setError('Chọn hoặc thêm ít nhất một trường.')
      return
    }
    await replace({ ...job.draft, metadata })
  }

  async function save() {
    if (!jobId) return
    let draft: unknown
    try { draft = JSON.parse(editor) } catch { setError('JSON không hợp lệ.'); return }
    await replace(draft)
  }

  function changeQuestion(update: (question: DraftQuestion) => void) {
    if (!job?.draft) return
    const draft = structuredClone(job.draft)
    const question = draft.sections.flatMap((section) => section.questions).find((item) => item.tmp_id === selectedQuestion)
    if (!question) return
    update(question)
    setJob({ ...job, draft })
    setQuestionsDirty(true)
  }

  const allQuestions = job?.draft?.sections.flatMap((section) => section.questions) || []
  const currentQuestion = allQuestions.find((question) => question.tmp_id === selectedQuestion)

  async function confirm() {
    if (!jobId) return
    setPending(true); setError('')
    try {
      const result = await api<{ exam_id: string }>(`/imports/${jobId}/confirm/`, { method: 'POST' })
      navigate(`/exams/${result.exam_id}`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể lưu đề.') }
    finally { setPending(false) }
  }

  async function discard() {
    if (!jobId) return
    setPending(true); setError('')
    try {
      const value = await api<Job>(`/imports/${jobId}/discard/`, { method: 'POST', body: JSON.stringify({ reason: discardReason }) })
      setJob(value)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể bỏ bản nháp.') }
    finally { setPending(false) }
  }

  async function retryPage(pageNo: number) {
    if (!jobId) return
    setPending(true); setError(''); setMessage('')
    try {
      await api(`/imports/${jobId}/pages/${pageNo}/retry/`, { method: 'POST' })
      setJob(await api<Job>(`/imports/${jobId}/`))
      setRetryVersion((version) => version + 1)
      setMessage(`Đã gửi lại trang ${pageNo} để phân tích.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể thử lại trang.') }
    finally { setPending(false) }
  }

  async function resolveIssue(index: number) {
    if (!jobId) return
    setPending(true); setError(''); setMessage('')
    try {
      const value = await api<Job>(`/imports/${jobId}/issues/${index}/resolve/`, {
        method: 'POST', body: JSON.stringify({ reason: resolutionReasons[index] || '' }),
      })
      setJob(value)
      setMessage('Đã ghi nhận việc đối chiếu trang nguồn và sửa bản nháp.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể xác nhận lỗi.') }
    finally { setPending(false) }
  }

  async function downloadOriginal() {
    if (!jobId || !job) return
    try {
      const blob = await apiBlob(`/imports/${jobId}/original/`)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = job.original_filename
      anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không tải được tệp gốc.') }
  }

  return <section className="paper manual-panel import-review-panel">
    <p className="eyebrow">THƯ VIỆN / KIỂM TRA BẢN NHÁP</p>
    <h1>{job?.draft_summary?.title || job?.original_filename || 'Lần nhập đề'}</h1>
    <ErrorText message={error} />
    {message && <p role="status">{message}</p>}
    {job && <>
      <p>Tệp: {job.original_filename}. Trạng thái: {statusLabels[job.status] || job.status}.
        {job.report && <> Nhận {job.report.valid} câu, bỏ qua {job.report.skipped} câu, {job.draft_summary?.chapters || 0} chương.</>}
      </p>
      <button type="button" className="text-button" onClick={() => { void downloadOriginal() }}>Tải tệp gốc</button>
      {processingStatuses.has(job.status) && <p role="status">Hệ thống đang xử lý từng trang. Trang này tự cập nhật khi bản nháp sẵn sàng.</p>}
      {job.status === 'FAILED' && <p role="alert">Không thể xử lý tệp ({job.error_code || 'không rõ nguyên nhân'}). Bạn có thể kiểm tra tệp gốc và nhập lại một tệp đã sửa.</p>}
      {job.source_kind === 'OCR' && !!job.pages?.length && <div className="import-source" role="region" aria-label="Trang nguồn">
        <div className="import-source-heading"><h2>Trang nguồn</h2><label>Trang <select value={selectedPage} onChange={(event) => setSelectedPage(Number(event.target.value))}>{job.pages.map((page) => <option key={page.page_no} value={page.page_no}>{page.page_no} · {page.status}</option>)}</select></label></div>
        {job.pages.find((page) => page.page_no === selectedPage)?.status === 'FAILED' && <p role="alert">Trang {selectedPage} chưa xử lý được: {job.pages.find((page) => page.page_no === selectedPage)?.error_code || 'Lỗi không xác định'}.
          {job.status === 'NEEDS_REVIEW' && <button type="button" className="button secondary" disabled={pending} onClick={() => { void retryPage(selectedPage) }}>Thử lại trang</button>}
        </p>}
        <div className="import-source-image"><PrivateImage path={`/imports/${job.id}/pages/${selectedPage}/image/`} alt={`Trang ${selectedPage} của ${job.original_filename}`} /></div>
      </div>}
      {!!job.report?.issues.length && <div role="region" aria-label="Báo cáo nhập đề"><h2>Báo cáo phân tích</h2><ul>{job.report.issues.map((issue, index) => <li key={index}>
        {issue.page_no ? `Trang ${issue.page_no}` : issue.line ? `Dòng ${issue.line}` : 'Toàn đề'}: {issue.code} — {issue.message}
        {issue.resolved_at && <span> · Đã đối chiếu</span>}
        {job.source_kind === 'OCR' && job.status === 'NEEDS_REVIEW' && issue.severity === 'ERROR' && !issue.resolved_at && resolvableCodes.has(issue.code) && <div className="import-issue-resolution">
          <label>Lý do xác nhận sau khi sửa bản nháp<input minLength={10} maxLength={500} value={resolutionReasons[index] || ''} onChange={(event) => setResolutionReasons((current) => ({ ...current, [index]: event.target.value }))} /></label>
          <button type="button" className="button secondary" disabled={pending || (resolutionReasons[index] || '').trim().length < 10 || questionsDirty || metadataDirty} onClick={() => { void resolveIssue(index) }}>Xác nhận đã sửa</button>
        </div>}
      </li>)}</ul></div>}
      {job.status === 'NEEDS_REVIEW' && <>
        <p>Kiểm tra nội dung và thông tin đề trước khi lưu. Nếu có lỗi, sửa bản nháp rồi lưu lại.</p>
        <form className="manual-form" onSubmit={saveMetadata}>
          <h2>Thông tin đề</h2>
          <label><span>Tên đề<span className="required-mark" aria-hidden="true"> *</span></span><input required maxLength={300} value={String(metadata.title || '')} onChange={(event) => field('title', event.target.value)} /></label>
          <div className="form-grid">
            <TaxonomyEntry kind="SUBJECT" label="Môn học" required suggestions={subjects.map((item) => item.name)} value={subjects.find((item) => item.code === metadata.subject)?.name || String(metadata.subject || '')} onChange={(value) => field('subject', value)} />
            <label><span>Cấp học<span className="required-mark" aria-hidden="true"> *</span></span><select required value={String(metadata.level || '')} onChange={(event) => { field('level', event.target.value); field('grade', null) }}><option value="">Chọn cấp</option><option value="TIEU_HOC">Tiểu học</option><option value="THCS">THCS</option><option value="THPT">THPT</option><option value="DAI_HOC">Đại học</option><option value="KHAC">Khác</option></select></label>
            {['TIEU_HOC', 'THCS', 'THPT'].includes(String(metadata.level || '')) && <label><span>Lớp<span className="required-mark" aria-hidden="true"> *</span></span><input required type="number" min={metadata.level === 'THPT' ? 10 : metadata.level === 'THCS' ? 6 : 1} max={metadata.level === 'THPT' ? 12 : metadata.level === 'THCS' ? 9 : 5} value={metadata.grade == null ? '' : String(metadata.grade)} onChange={(event) => field('grade', event.target.value ? Number(event.target.value) : null)} /></label>}
            <label><span>Loại đề<span className="required-mark" aria-hidden="true"> *</span></span><select required value={String(metadata.exam_type || '')} onChange={(event) => field('exam_type', event.target.value)}><option value="">Chọn loại</option><option value="ON_TAP">Ôn tập</option><option value="KIEM_TRA">Kiểm tra</option><option value="GIUA_KY">Giữa kỳ</option><option value="CUOI_KY">Cuối kỳ</option><option value="THI_CHINH_THUC">Thi chính thức</option><option value="OLYMPIC">Olympic</option><option value="KHAC">Khác</option></select></label>
            <label><span>Thời gian (phút){metadata.duration_minutes != null && <span className="required-mark" aria-hidden="true"> *</span>}</span><input type="number" min={1} max={300} required={metadata.duration_minutes != null} disabled={metadata.duration_minutes == null} value={metadata.duration_minutes == null ? '' : String(metadata.duration_minutes)} onChange={(event) => field('duration_minutes', event.target.value ? Number(event.target.value) : null)} /></label>
          </div>
          <label className="check-label"><input type="checkbox" checked={metadata.duration_minutes == null} onChange={(event) => field('duration_minutes', event.target.checked ? null : 30)} /> Không giới hạn thời gian (chỉ luyện tập)</label>
          <TaxonomyNames kind="SCHOOL" label="Trường" values={Array.isArray(metadata.schools) ? metadata.schools as string[] : []} onChange={(values) => fieldList('schools', values)} required />
          <TaxonomyNames kind="MAJOR" label="Ngành" values={Array.isArray(metadata.majors) ? metadata.majors as string[] : []} onChange={(values) => fieldList('majors', values)} />
          <label>Nguồn đề<input maxLength={300} value={String(metadata.source || '')} onChange={(event) => field('source', event.target.value)} /></label>
          <button type="submit" className="button secondary" disabled={pending}>Lưu thông tin đề</button>
        </form>
        {allQuestions.length > 0 && <div className="manual-form" role="region" aria-label="Kiểm tra câu hỏi">
          <h2>Kiểm tra câu hỏi</h2>
          <label>Chọn câu hỏi<select value={selectedQuestion} onChange={(event) => setSelectedQuestion(event.target.value)}>{job.draft?.sections.flatMap((section, sectionIndex) => section.questions.map((question) => <option key={question.tmp_id} value={question.tmp_id}>{section.title || `Phần ${sectionIndex + 1}`} · Câu {question.order}</option>))}</select></label>
          {currentQuestion && <>
            <p>Loại: {currentQuestion.kind}</p>
            <label>Nội dung câu hỏi<textarea value={currentQuestion.text} onChange={(event) => changeQuestion((question) => { question.text = event.target.value })} /></label>
            {['MCQ', 'MCQ_MULTI'].includes(currentQuestion.kind) && <fieldset className="review-answers"><legend>Đáp án</legend>{currentQuestion.choices.map((choice, index) => <div className="review-answer-row" key={choice.label}>
              <label>{choice.label}<input value={choice.text} onChange={(event) => changeQuestion((question) => { question.choices[index].text = event.target.value })} /></label>
              <label className="review-answer-key"><input type={currentQuestion.kind === 'MCQ' ? 'radio' : 'checkbox'} name={`answer-${currentQuestion.tmp_id}`} checked={choice.is_correct} onChange={() => changeQuestion((question) => { question.choices.forEach((item, answerIndex) => { item.is_correct = currentQuestion.kind === 'MCQ' ? answerIndex === index : answerIndex === index ? !item.is_correct : item.is_correct }) })} /> Đúng</label>
            </div>)}</fieldset>}
            <label>Giải thích (không bắt buộc)<textarea value={currentQuestion.explanation || ''} onChange={(event) => changeQuestion((question) => { question.explanation = event.target.value })} /></label>
            <button type="button" className="button secondary" disabled={pending || !questionsDirty || metadataDirty} onClick={() => replace(job.draft)}>Lưu câu hỏi</button>
          </>}
        </div>}
        <div className="review-final-actions">
          <button type="button" className="button secondary" onClick={() => { setEditor(JSON.stringify(job.draft, null, 2)); setEditing(!editing) }}>{editing ? 'Đóng trình sửa' : 'Sửa bản nháp JSON'}</button>
          {editing && <div><label>Bản nháp JSON<textarea className="draft-editor" value={editor} onChange={(event) => setEditor(event.target.value)} /></label><button type="button" className="button secondary" disabled={pending} onClick={save}>Lưu bản nháp</button></div>}
          <label>Lý do bỏ bản nháp (không bắt buộc)<input maxLength={500} value={discardReason} onChange={(event) => setDiscardReason(event.target.value)} /></label>
          <div className="form-actions"><button type="button" className="button primary" disabled={pending || metadataDirty || questionsDirty || !!job.report?.issues.some((item) => item.severity === 'ERROR' && !item.resolved_at) || !String(metadata.title || '').trim() || !String(metadata.subject || '').trim() || !Array.isArray(metadata.schools) || metadata.schools.length === 0 || !metadata.level || !metadata.exam_type || (['TIEU_HOC', 'THCS', 'THPT'].includes(String(metadata.level)) && !metadata.grade)} onClick={confirm}>Lưu đề riêng tư</button><button type="button" className="button secondary" disabled={pending} onClick={discard}>Bỏ bản nháp</button></div>
        </div>
      </>}
      {job.status === 'REJECTED' && job.discard_reason && <p>Lý do bỏ: {job.discard_reason}</p>}
      {job.exam_id && <Link to={`/exams/${job.exam_id}`}>Xem đề đã lưu</Link>}
    </>}
  </section>
}
