import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'

type Summary = {
  build_sha: string
  import_jobs_by_status: Record<string, number>
  oldest_import_review_age_seconds: number | null
  pending_publication_requests: number
}

const statusNames: Record<string, string> = {
  UPLOADED: 'Đã tải lên', INGESTING: 'Đang nhận tệp', EXTRACTING: 'Đang trích xuất',
  ASSEMBLING: 'Đang ghép', NEEDS_REVIEW: 'Chờ kiểm tra', APPROVED: 'Đã xác nhận',
  REJECTED: 'Đã loại bỏ', FAILED: 'Lỗi',
}

export function OperationsPage() {
  const { api, user } = useAuth()
  const apiOrigin = new URL(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1', window.location.origin).origin
  const summary = useQuery({ queryKey: ['ops-summary'], queryFn: () => api<Summary>('/ops/summary/') })
  if (!user?.roles.includes('Admin')) return <section className="paper account-panel"><h1>Không có quyền truy cập</h1></section>
  if (summary.isPending) return <p role="status">Đang tải tình trạng vận hành…</p>
  if (summary.isError) return <section className="paper account-panel"><h1>Không thể tải vận hành</h1><p role="alert">{summary.error.message}</p></section>
  return <section className="paper account-panel">
    <p className="eyebrow">TESTFLOW / VẬN HÀNH</p>
    <h1>Tình trạng hệ thống</h1>
    <p>Phiên bản: <code>{summary.data.build_sha}</code></p>
    <p>Yêu cầu công khai chờ duyệt: {summary.data.pending_publication_requests}. <Link to="/publish-requests">Mở hàng đợi</Link></p>
    <h2>Nhập đề</h2>
    <dl>{Object.entries(summary.data.import_jobs_by_status).map(([key, count]) => <div key={key}><dt>{statusNames[key] || key}</dt><dd>{count}</dd></div>)}</dl>
    <p>Job chờ kiểm tra lâu nhất: {summary.data.oldest_import_review_age_seconds === null ? 'Không có' : `${Math.round(summary.data.oldest_import_review_age_seconds / 60)} phút`}.</p>
    <p><a href={`${apiOrigin}/healthz`}>Kiểm tra DB và Redis</a></p>
  </section>
}
