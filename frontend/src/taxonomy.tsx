import { useState } from 'react'
import { useAuth } from './auth'

type Kind = 'SUBJECT' | 'SCHOOL' | 'MAJOR'
type Match = { id: number; name: string; code: string | null }
type Lookup = { match: Match | null; suggestions: Match[] }

export function TaxonomyEntry({ kind, label, value, onChange, onConfirmed }: {
  kind: Kind; label: string; value: string; onChange: (value: string) => void
  onConfirmed?: (name: string) => void
}) {
  const { api } = useAuth()
  const [lookup, setLookup] = useState<Lookup | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function check() {
    if (!value.trim()) return
    setBusy(true); setMessage(''); setLookup(null)
    try {
      const result = await api<Lookup>(`/taxonomy/lookup/?kind=${kind}&name=${encodeURIComponent(value)}`)
      setLookup(result)
      if (result.match) { onChange(result.match.name); onConfirmed?.(result.match.name) }
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không tra cứu được danh mục.') }
    finally { setBusy(false) }
  }

  async function propose() {
    setBusy(true); setMessage('')
    try {
      const result = await api<{ id?: number; match?: Match }>('/taxonomy/proposals/', {
        method: 'POST', body: JSON.stringify({ kind, name: value }),
      })
      if (result.match) { onChange(result.match.name); onConfirmed?.(result.match.name) }
      else setMessage(`Đã gửi đề xuất #${result.id}. Bạn có thể dùng tên này sau khi Admin duyệt.`)
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không gửi được đề xuất.') }
    finally { setBusy(false) }
  }

  return <div className="taxonomy-entry">
    <label>{label}<input maxLength={200} value={value} onChange={(event) => {
      onChange(event.target.value); setLookup(null); setMessage('')
    }} /></label>
    <button type="button" disabled={busy || !value.trim()} onClick={check}>Kiểm tra tên</button>
    {busy && <p role="status">Đang tra cứu…</p>}
    {lookup?.match && <p role="status">Tên chuẩn: {lookup.match.name}</p>}
    {lookup && !lookup.match && <div>
      {lookup.suggestions.length > 0 && <p>Có thể bạn muốn chọn: {lookup.suggestions.map((item) => <button
        key={item.id} type="button" onClick={() => { onChange(item.name); onConfirmed?.(item.name); setLookup({ match: item, suggestions: [] }) }}
      >{item.name}</button>)}</p>}
      <button type="button" disabled={busy} onClick={propose}>Đề xuất tên mới</button>
    </div>}
    {message && <p role="status">{message}</p>}
  </div>
}

export function TaxonomyNames({ kind, label, values, onChange }: {
  kind: 'SCHOOL' | 'MAJOR'; label: string; values: string[]; onChange: (values: string[]) => void
}) {
  const [input, setInput] = useState('')
  return <fieldset className="taxonomy-names"><legend>{label}</legend>
    {values.map((name) => <span key={name} className="taxonomy-chip">{name} <button type="button" aria-label={`Bỏ ${name}`} onClick={() => onChange(values.filter((item) => item !== name))}>×</button></span>)}
    <TaxonomyEntry kind={kind} label={`Thêm ${label.toLowerCase()}`} value={input} onChange={setInput}
      onConfirmed={(name) => { if (!values.includes(name)) onChange([...values, name]); setInput('') }} />
  </fieldset>
}
