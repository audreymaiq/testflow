import { useId, useRef, useState } from 'react'
import { useAuth } from './auth'

type Kind = 'SUBJECT' | 'SCHOOL' | 'MAJOR'
type Match = { id: number; name: string; code: string | null }
type Lookup = { match: Match | null; suggestions: Match[] }

export function TaxonomyEntry({ kind, label, value, onChange, onConfirmed, required = false, suggestions = [] }: {
  kind: Kind; label: string; value: string; onChange: (value: string) => void
  onConfirmed?: (name: string) => void
  required?: boolean; suggestions?: string[]
}) {
  const { api } = useAuth()
  const [lookup, setLookup] = useState<Lookup | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [hasFormula, setHasFormula] = useState(false)
  const currentValue = useRef(value)
  const suggestionsId = useId()
  currentValue.current = value

  async function check() {
    if (!value.trim()) return
    const query = value
    setBusy(true); setMessage(''); setLookup(null)
    try {
      const result = await api<Lookup>(`/taxonomy/lookup/?kind=${kind}&name=${encodeURIComponent(query)}`)
      if (currentValue.current !== query) return
      setLookup(result)
      if (result.match) { onChange(result.match.name); onConfirmed?.(result.match.name) }
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không tra cứu được danh mục.') }
    finally { setBusy(false) }
  }

  async function createName() {
    const name = value
    setBusy(true); setMessage('')
    try {
      const result = await api<{ match: Match; created: boolean }>('/taxonomy/names/', {
        method: 'POST', body: JSON.stringify({ kind, name, has_formula: hasFormula }),
      })
      setLookup({ match: result.match, suggestions: [] })
      onChange(result.match.name); onConfirmed?.(result.match.name)
      setMessage(result.created ? 'Đã tạo tên mới.' : 'Đã chọn tên chuẩn có sẵn.')
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Không tạo được tên mới.') }
    finally { setBusy(false) }
  }

  return <div className="taxonomy-entry">
    <label><span>{label}{required && <span className="required-mark" aria-hidden="true"> *</span>}</span><input required={required} list={suggestions.length ? suggestionsId : undefined} disabled={busy} maxLength={kind === 'SUBJECT' ? 120 : 200} value={value} onChange={(event) => {
      onChange(event.target.value); setLookup(null); setMessage('')
    }} /></label>
    {suggestions.length > 0 && <datalist id={suggestionsId}>{suggestions.map((name) => <option key={name} value={name} />)}</datalist>}
    <button type="button" disabled={busy || !value.trim()} onClick={check}>Kiểm tra tên</button>
    {busy && <p role="status">Đang xử lý…</p>}
    {lookup?.match && <p role="status">Tên chuẩn: {lookup.match.name}</p>}
    {lookup && !lookup.match && <div>
      {lookup.suggestions.length > 0 && <p>Có thể bạn muốn chọn: {lookup.suggestions.map((item) => <button
        key={item.id} type="button" onClick={() => { onChange(item.name); onConfirmed?.(item.name); setLookup({ match: item, suggestions: [] }) }}
      >{item.name}</button>)}</p>}
      <p>Nếu không tên nào đúng, bạn có thể tạo một tên riêng. Tên này sẽ xuất hiện trong danh mục.</p>
      {kind === 'SUBJECT' && <label><input type="checkbox" checked={hasFormula} onChange={(event) => setHasFormula(event.target.checked)} /> Môn có công thức</label>}
      <button type="button" disabled={busy} onClick={createName}>Tạo tên mới</button>
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
