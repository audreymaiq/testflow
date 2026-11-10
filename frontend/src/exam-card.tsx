import { Link } from 'react-router-dom'
import { DeckMark } from './exam-art'

export const levelNames: Record<string, string> = {
  TIEU_HOC: 'Tiểu học', THCS: 'THCS', THPT: 'THPT', DAI_HOC: 'Đại học', KHAC: 'Khác',
}

export const examTypeNames: Record<string, string> = {
  THI_CHINH_THUC: 'Đề thi chính thức', GIUA_KY: 'Đề giữa kỳ', CUOI_KY: 'Đề cuối kỳ',
  KIEM_TRA: 'Đề kiểm tra', ON_TAP: 'Đề ôn tập', OLYMPIC: 'Đề Olympic', KHAC: 'Đề khác',
}

export type ExamCardData = {
  id: string; title: string; subtitle: string; subject: string; level: string; grade: number | null
  exam_type: string; visibility: string; question_count: number; duration_minutes: number | null
  icon: string; color: string; is_system_sample: boolean; schools: string[]
}

export function ExamCard({ exam }: { exam: ExamCardData }) {
  const schoolLabel = exam.schools.length > 0 ? exam.schools.join(', ') : 'Chưa cập nhật'
  return <Link className="exam-card" to={`/exams/${exam.id}`}>
    <span className="exam-card-cover">
      <span className="exam-card-type">{examTypeNames[exam.exam_type] || 'Đề thi'}</span>
      {exam.visibility === 'PRIVATE' && <span className="exam-card-private">Riêng tư</span>}
      <span className="exam-card-mark"><DeckMark title={exam.subject} icon={exam.icon} color={exam.color} /></span>
    </span>
    <span className="exam-card-body">
      <strong className="exam-card-subject">{exam.subject}</strong>
      <span className="exam-card-meta">{exam.grade ? `Lớp ${exam.grade}` : levelNames[exam.level] || exam.level}</span>
      <strong className="exam-card-title">{exam.title} {exam.is_system_sample && <span className="sample-badge">Bộ mẫu</span>}</strong>
      {exam.subtitle && <small>{exam.subtitle}</small>}
      <span className="exam-card-school"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 8h16M4 8l6-5 6 5M5 8v8m4-8v8m4-8v8m3-8v8M2 17h16" /></svg><span>Trường: {schoolLabel}</span></span>
      <span className="exam-card-foot">
        <span><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="7" /><path d="M10 5v5l3 2" /></svg>{exam.duration_minutes ? `${exam.duration_minutes} phút` : 'Không giới hạn giờ'}</span>
        <span><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m3 7 7-4 7 4-7 4-7-4Zm0 4 7 4 7-4M3 15l7 4 7-4" /></svg>{exam.question_count} câu</span>
        <span className="exam-card-arrow" aria-hidden="true">→</span>
      </span>
    </span>
  </Link>
}
