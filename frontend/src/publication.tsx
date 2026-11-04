import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './auth'

type RequestSummary = {
  id: number; exam: string; exam_title: string; source: string; owner_name: string
  status: string; reason: string; created_at: string; decided_at: string | null
}
type ReviewQuestion = {
  tmp_id: string; text: string; kind: string; explanation: string
  choices: { label: string; text: string; is_correct: boolean }[]
  statements: { label: string; text: string; is_true: boolean | null }[]
  short_answer: string | null; tf_answer: boolean | null
}
type RequestDetail = RequestSummary & {
  draft: { metadata: { title: string; source: string }; sections: { title: string; questions: ReviewQuestion[] }[] }
}
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }

export function PublicationQueuePage() {
  const { api } = useAuth()
  const [page, setPage] = useState(1)
  const queue = useQuery({ queryKey: ['publish-requests', page], queryFn: () => api<Page<RequestSummary>>(`/publish-requests/?page=${page}`) })
  return <section className="paper practice-panel">
    <p className="eyebrow">KIỂM DUYỆT</p><h1>Yêu cầu công khai</h1>
    {queue.isPending && <p role="status">Đang tải hàng đợi…</p>}
    {queue.isError && <p role="alert">{queue.error.message}</p>}
    {queue.data?.count === 0 && <p>Hiện không có yêu cầu chờ duyệt.</p>}
    {queue.data?.results.map((item) => <article className="history-item" key={item.id}>
      <div><h2>{item.exam_title}</h2><p>Nguồn: {item.source} · Người gửi: {item.owner_name}</p></div>
      <Link to={`/publish-requests/${item.id}`}>Xem và duyệt</Link>
    </article>)}
    {queue.data && <nav className="pagination" aria-label="Phân trang yêu cầu">
      <button disabled={!queue.data.previous} onClick={() => setPage(page - 1)}>Trang trước</button>
      <span>Trang {page}</span>
      <button disabled={!queue.data.next} onClick={() => setPage(page + 1)}>Trang sau</button>
    </nav>}
  </section>
}

export function PublicationDetailPage() {
  const { requestId } = useParams()
  const { api } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const review = useQuery({ queryKey: ['publish-request', requestId], queryFn: () => api<RequestDetail>(`/publish-requests/${requestId}/`) })

  async function decide(decision: 'approve' | 'reject') {
    setPending(true); setError('')
    try {
      await api(`/publish-requests/${requestId}/${decision}/`, {
        method: 'POST', body: JSON.stringify({ reason }),
      })
      await queryClient.invalidateQueries({ queryKey: ['publish-requests'] })
      navigate('/publish-requests')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể quyết định yêu cầu.') }
    finally { setPending(false) }
  }

  if (review.isPending) return <p role="status">Đang tải đề cần duyệt…</p>
  if (review.isError) return <section className="paper practice-panel"><h1>Không mở được yêu cầu</h1><p role="alert">{review.error.message}</p></section>
  return <section className="paper practice-panel">
    <Link to="/publish-requests">← Hàng đợi</Link>
    <p className="eyebrow">YÊU CẦU #{review.data.id}</p><h1>{review.data.exam_title}</h1>
    <p>Nguồn: {review.data.source}</p><p>Người gửi: {review.data.owner_name}</p>
    {review.data.draft.sections.map((section, sectionIndex) => <section key={sectionIndex} className="review-section">
      <h2>{section.title}</h2>
      {section.questions.map((question) => <article key={question.tmp_id} className="result-question">
        <h3>{question.kind}</h3><p>{question.text}</p>
        {question.choices.map((choice) => <p key={choice.label}>{choice.label}. {choice.text}{choice.is_correct && <strong> · Đáp án</strong>}</p>)}
        {question.statements.map((statement) => <p key={statement.label}>{statement.label}. {statement.text} — {statement.is_true === null ? 'Chưa có đáp án' : statement.is_true ? 'Đúng' : 'Sai'}</p>)}
        {question.short_answer && <p>Đáp án ngắn: {question.short_answer}</p>}
        {question.tf_answer !== null && <p>Đáp án đúng sai: {question.tf_answer ? 'Đúng' : 'Sai'}</p>}
        {question.explanation && <p>Giải thích: {question.explanation}</p>}
      </article>)}
    </section>)}
    {review.data.status === 'PENDING' && <div className="review-decision">
      <label>Lý do hoặc ghi chú<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="practice-actions">
        <button type="button" className="button primary" disabled={pending} onClick={() => decide('approve')}>Duyệt công khai</button>
        <button type="button" className="button secondary" disabled={pending || !reason.trim()} onClick={() => decide('reject')}>Từ chối</button>
      </div>
    </div>}
  </section>
}
