import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Modal } from './shared'
import { TaxonomyEntry, TaxonomyNames } from './taxonomy'

type Issue = { line: number; code: string; message: string; severity: 'ERROR' | 'WARNING' }
type DraftChoice = { label: string; text: string; is_correct: boolean }
type DraftQuestion = { tmp_id: string; order: number; kind: string; text: string; explanation: string; choices: DraftChoice[] }
type ImportDraft = { metadata: Record<string, unknown>; sections: { title: string; questions: DraftQuestion[] }[] }
type Job = {
  id: string
  status: string
  original_filename: string
  exam_id: string | null
  discard_reason?: string
  report: { valid: number; skipped: number; issues: Issue[] }
  draft_summary: { title: string | null; questions: number; chapters: number }
  draft?: ImportDraft
}

function ErrorText({ message }: { message: string }) {
  return message ? <p role="alert" className="form-error">{message}</p> : null
}

export function AddExamPage() {
  return <section className="paper manual-panel add-exam-panel">
    <p className="eyebrow">THƯ VIỆN / THÊM ĐỀ</p>
    <h1>Thêm đề</h1>
    <div className="add-exam-options">
      <Link to="/exams/new"><span className="add-exam-option-index">01</span><strong>Tạo đề mới</strong><span>Viết câu hỏi và đáp án trực tiếp.</span><span aria-hidden="true">↗</span></Link>
      <Link to="/imports/new"><span className="add-exam-option-index">02</span><strong>Thêm đề có sẵn</strong><span>Nhập tệp TXT, xem lại câu hỏi rồi lưu đề.</span><span aria-hidden="true">↗</span></Link>
    </div>
  </section>
}

export function TxtImportPage() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
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
    <form onSubmit={submit}>
      <label>Chọn tệp .txt<input type="file" accept=".txt,text/plain" required onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
      <ErrorText message={error} />
      <button className="button primary" type="submit" disabled={!file || pending}>{pending ? 'Đang phân tích…' : 'Xác nhận'}</button>
    </form>
    <p><Link to="/imports">Xem các tệp đã nhập</Link></p>
    {showGuide && <Modal title="Định dạng tệp TXT" onClose={() => setShowGuide(false)}>
      <p>Mỗi câu hỏi nằm trong một chương. Viết câu hỏi, các lựa chọn A–F, rồi một dòng đáp án bắt đầu bằng <code>=&gt;</code>. Ví dụ tương thích Quiz Rush v1:</p>
      <pre className="txt-format-example"><code>{`#TITLE: Ôn tập
[CH1] Số học
2 + 2 bằng bao nhiêu?
A. 3
B. 4
=>B`}</code></pre>
      <p>TXT v2 có thể thêm <code>#SUBJECT</code>, <code>#LEVEL</code>, <code>#GRADE</code>, <code>#TYPE</code> và các trường khác ở đầu tệp. Các dạng đáp án thêm:</p>
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
  const { api } = useAuth()
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

  useEffect(() => {
    if (!jobId) return
    let active = true
    api<Job>(`/imports/${jobId}/`).then((value) => {
      if (!active) return
      setJob(value)
      setEditor(JSON.stringify(value.draft, null, 2))
      setMetadata((value.draft?.metadata || {}) as Record<string, unknown>)
      setMetadataDirty(false)
      setQuestionsDirty(false)
      setSelectedQuestion(value.draft?.sections.flatMap((section) => section.questions)[0]?.tmp_id || '')
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Không tải được bản nháp.')
    })
    return () => { active = false }
  }, [jobId])

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

  return <section className="paper manual-panel">
    <p className="eyebrow">THƯ VIỆN / KIỂM TRA BẢN NHÁP</p>
    <h1>{job?.draft_summary?.title || job?.original_filename || 'Bản nháp TXT'}</h1>
    <ErrorText message={error} />
    {message && <p role="status">{message}</p>}
    {job && <>
      <p>Tệp: {job.original_filename}. Trạng thái: {job.status}. Nhận {job.report.valid} câu, bỏ qua {job.report.skipped} câu, {job.draft_summary.chapters} chương.</p>
      {job.report.issues.length > 0 && <div role="region" aria-label="Báo cáo nhập TXT"><h2>Báo cáo</h2><ul>{job.report.issues.map((issue, index) => <li key={index}>Dòng {issue.line}: {issue.code} — {issue.message}</li>)}</ul></div>}
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
          </div>
          <TaxonomyNames kind="SCHOOL" label="Trường" values={Array.isArray(metadata.schools) ? metadata.schools as string[] : []} onChange={(values) => fieldList('schools', values)} />
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
          <div className="form-actions"><button type="button" className="button primary" disabled={pending || metadataDirty || questionsDirty || job.report.issues.some((item) => item.severity === 'ERROR') || !String(metadata.title || '').trim() || !String(metadata.subject || '').trim() || !metadata.level || !metadata.exam_type || (['TIEU_HOC', 'THCS', 'THPT'].includes(String(metadata.level)) && !metadata.grade)} onClick={confirm}>Lưu đề riêng tư</button><button type="button" className="button secondary" disabled={pending} onClick={discard}>Bỏ bản nháp</button></div>
        </div>
      </>}
      {job.status === 'REJECTED' && job.discard_reason && <p>Lý do bỏ: {job.discard_reason}</p>}
      {job.exam_id && <Link to={`/exams/${job.exam_id}`}>Xem đề đã lưu</Link>}
    </>}
  </section>
}
