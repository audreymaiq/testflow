import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from './auth'

type Summary = {
  build_sha: string
  import_jobs_by_status: Record<string, number>
  oldest_import_review_age_seconds: number | null
  pending_publication_requests: number
}

type Proposal = { id: number; kind: 'SUBJECT' | 'SCHOOL' | 'MAJOR'; name: string; requested_by_name: string; created_at: string }
type Match = { id: number; name: string }

function ProposalRow({ proposal }: { proposal: Proposal }) {
  const { api } = useAuth()
  const queryClient = useQueryClient()
  const [canonicalName, setCanonicalName] = useState(proposal.name)
  const [reason, setReason] = useState('')
  const [mappingQuery, setMappingQuery] = useState(proposal.name)
  const [mappingResults, setMappingResults] = useState<Match[]>([])
  const [levels, setLevels] = useState<string[]>([])
  const [hasFormula, setHasFormula] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const lookup = useQuery({
    queryKey: ['taxonomy-suggest', proposal.id],
    queryFn: () => api<{ suggestions: Match[] }>(`/taxonomy/lookup/?kind=${proposal.kind}&name=${encodeURIComponent(proposal.name)}`),
  })
  async function searchMapping() {
    setMessage('')
    try {
      const result = await api<{ match: Match | null; suggestions: Match[] }>(`/taxonomy/lookup/?kind=${proposal.kind}&name=${encodeURIComponent(mappingQuery)}`)
      setMappingResults(result.match ? [result.match] : result.suggestions)
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không tra cứu được tên chuẩn.') }
  }
  async function decide(action: 'MAP' | 'CREATE' | 'REJECT', target_id?: number) {
    setBusy(true); setMessage('')
    try {
      await api(`/taxonomy/proposals/${proposal.id}/decision/`, {
        method: 'POST', body: JSON.stringify({ action, target_id, canonical_name: canonicalName, levels, has_formula: hasFormula, reason }),
      })
      await queryClient.invalidateQueries({ queryKey: ['taxonomy-pending'] })
      await queryClient.invalidateQueries({ queryKey: ['subjects'] })
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không xử lý được đề xuất.') }
    finally { setBusy(false) }
  }
  return <li className="taxonomy-proposal">
    <strong>{proposal.kind}: {proposal.name}</strong> · {proposal.requested_by_name}
    {lookup.data?.suggestions.length ? <p>Tên gần giống: {lookup.data.suggestions.map((item) => <button key={item.id} type="button" disabled={busy} onClick={() => decide('MAP', item.id)}>Gộp vào {item.name}</button>)}</p> : null}
    <label>Tìm tên chuẩn để gộp<input value={mappingQuery} onChange={(event) => setMappingQuery(event.target.value)} /></label>
    <button type="button" onClick={searchMapping} disabled={busy || !mappingQuery.trim()}>Tìm tên chuẩn</button>
    {mappingResults.map((item) => <button key={item.id} type="button" disabled={busy} onClick={() => decide('MAP', item.id)}>Gộp vào {item.name}</button>)}
    <label>Tên chuẩn mới<input value={canonicalName} onChange={(event) => setCanonicalName(event.target.value)} /></label>
    {proposal.kind === 'SUBJECT' && <fieldset><legend>Cấp áp dụng (để trống nếu dùng mọi cấp)</legend>{['TIEU_HOC', 'THCS', 'THPT', 'DAI_HOC', 'KHAC'].map((level) => <label key={level}><input type="checkbox" checked={levels.includes(level)} onChange={(event) => setLevels(event.target.checked ? [...levels, level] : levels.filter((item) => item !== level))} />{level}</label>)}<label><input type="checkbox" checked={hasFormula} onChange={(event) => setHasFormula(event.target.checked)} />Có công thức</label></fieldset>}
    <label>Lý do (bắt buộc khi từ chối)<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    <button type="button" disabled={busy} onClick={() => decide('CREATE')}>Tạo tên chuẩn</button>{' '}
    <button type="button" disabled={busy || !reason.trim()} onClick={() => decide('REJECT')}>Từ chối</button>
    {message && <p role="alert">{message}</p>}
  </li>
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
  const proposals = useQuery({ queryKey: ['taxonomy-pending'], queryFn: () => api<{ results: Proposal[]; count: number }>('/taxonomy/proposals/pending/'), enabled: !!user?.roles.includes('Admin') })
  if (!user?.roles.includes('Admin')) return <section className="paper account-panel"><h1>Không có quyền truy cập</h1></section>
  if (summary.isPending) return <p role="status">Đang tải tình trạng vận hành…</p>
  if (summary.isError) return <section className="paper account-panel"><h1>Không thể tải vận hành</h1><p role="alert">{summary.error.message}</p></section>
  return <section className="paper account-panel">
    <p className="eyebrow">TESTFLOW / VẬN HÀNH</p>
    <h1>Tình trạng hệ thống</h1>
    <p>Phiên bản: <code>{summary.data.build_sha}</code></p>
    <p>Yêu cầu công khai chờ duyệt: {summary.data.pending_publication_requests}. <Link to="/publish-requests">Mở hàng đợi</Link></p>
    <h2>Đề xuất môn, trường, ngành</h2>
    {proposals.isPending ? <p>Đang tải hàng đợi…</p> : proposals.isError ? <p role="alert">{proposals.error.message}</p> : proposals.data?.count ? <ul>{proposals.data.results.map((proposal) => <ProposalRow key={proposal.id} proposal={proposal} />)}</ul> : <p>Không có đề xuất chờ duyệt.</p>}
    <h2>Nhập đề</h2>
    <dl>{Object.entries(summary.data.import_jobs_by_status).map(([key, count]) => <div key={key}><dt>{statusNames[key] || key}</dt><dd>{count}</dd></div>)}</dl>
    <p>Job chờ kiểm tra lâu nhất: {summary.data.oldest_import_review_age_seconds === null ? 'Không có' : `${Math.round(summary.data.oldest_import_review_age_seconds / 60)} phút`}.</p>
    <p><a href={`${apiOrigin}/healthz`}>Kiểm tra DB và Redis</a></p>
  </section>
}
