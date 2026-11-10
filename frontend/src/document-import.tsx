import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'

type ImportResponse = { id: string }

export function DocumentImportPage() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [subjectHint, setSubjectHint] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    if (file.size > (file.type.startsWith('image/') ? 10 : 20) * 1024 * 1024) {
      setError('Ảnh tối đa 10 MB; PDF hoặc DOCX tối đa 20 MB.')
      return
    }
    setPending(true)
    setError('')
    try {
      const body = new FormData()
      body.append('file', file)
      if (subjectHint.trim()) body.append('subject_hint', subjectHint.trim())
      const job = await api<ImportResponse>('/imports/document/', { method: 'POST', body })
      navigate(`/imports/${job.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể gửi tệp.')
    } finally {
      setPending(false)
    }
  }

  return <section className="paper manual-panel">
    <p className="eyebrow">THƯ VIỆN / THÊM ĐỀ CÓ SẴN</p>
    <h1>Thêm đề từ tài liệu</h1>
    <p className="lede">Tải PDF, DOCX hoặc ảnh đề thi. Hệ thống phân tích từng trang; bạn kiểm tra câu hỏi, đáp án và thông tin đề trước khi lưu riêng tư.</p>
    <form className="manual-form" onSubmit={submit}>
      <label>Chọn PDF, DOCX hoặc ảnh<input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg,image/webp" required onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
      <p>Ảnh tối đa 10 MB; PDF hoặc DOCX tối đa 20 MB. Tệp nhiều trang có thể cần thêm thời gian xử lý.</p>
      <label>Môn học gợi ý (không bắt buộc)<input maxLength={40} value={subjectHint} onChange={(event) => setSubjectHint(event.target.value)} placeholder="Ví dụ: Toán học" /></label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button className="button primary" type="submit" disabled={!file || pending}>{pending ? 'Đang gửi tệp…' : 'Thêm đề'}</button>
    </form>
    <p><Link to="/imports/new">Nhập tệp TXT</Link> · <Link to="/imports">Các lần nhập đề</Link></p>
  </section>
}
