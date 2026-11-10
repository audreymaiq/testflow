type DeckMarkProps = { title: string; icon: string; color: string }

export function DeckMark({ title, icon, color }: DeckMarkProps) {
  const legacyEye = icon.replace(/\uFE0F/g, '') === '\u{1F441}'
  const subject = title.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('vi-VN')
  const glyph = legacyEye ? <><path d="M3 16c3.5-5 7.8-7.5 13-7.5S25.5 11 29 16c-3.5 5-7.8 7.5-13 7.5S6.5 21 3 16Z" /><circle cx="16" cy="16" r="3.5" /></>
    : subject.startsWith('toan') ? <><rect x="7" y="4" width="18" height="24" rx="2" /><path d="M11 10h10M12 16h3m-1.5-1.5v3m5-1.5h3m-9 7h3m4-1.5 3 3m0-3-3 3" /></>
    : subject.startsWith('vat ly') ? <><ellipse cx="16" cy="16" rx="12" ry="4" transform="rotate(45 16 16)" /><ellipse cx="16" cy="16" rx="12" ry="4" transform="rotate(-45 16 16)" /><circle cx="16" cy="16" r="2" fill="currentColor" /></>
    : subject.startsWith('hoa') ? <><path d="M12 4h8m-6 0v9L7 25a2 2 0 0 0 2 3h14a2 2 0 0 0 2-3l-7-12V4M10 22h12" /></>
    : subject.startsWith('sinh') ? <><path d="M27 5C13 5 6 12 6 21c0 4 3 6 7 6 9 0 14-8 14-22ZM9 24c5-6 9-10 15-13" /></>
    : subject.startsWith('tieng anh') ? <><path d="M5 25 12 6l7 19M8 18h8m12-10h7v13h-7l-4 4V8Z" /></>
    : subject.startsWith('ngu van') ? <><path d="M16 27c-4-3-8-4-12-3V7c5-1 9 0 12 3 3-3 7-4 12-3v17c-4-1-8 0-12 3ZM16 10v17" /></>
    : subject.startsWith('lich su') ? <><path d="M4 12h24M6 12l10-7 10 7M8 12v13m5-13v13m6-13v13m5-13v13M4 27h24" /></>
    : subject.startsWith('dia ly') ? <><circle cx="16" cy="16" r="12" /><path d="M4 16h24M16 4c-7 7-7 17 0 24m0-24c7 7 7 17 0 24" /></>
    : <path d="M16 27c-4-3-8-4-12-3V7c5-1 9 0 12 3 3-3 7-4 12-3v17c-4-1-8 0-12 3ZM16 10v17" />
  return <span className="home-deck-mark" aria-hidden="true"
    style={/^#[0-9a-fA-F]{6}$/.test(color) ? { borderColor: color } : undefined}>
    <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{glyph}</svg>
  </span>
}

export function AnswerSheetArt() {
  return <svg viewBox="0 0 240 120" fill="none" aria-hidden="true">
    <g transform="rotate(-8 169 66)" stroke="currentColor" strokeWidth="1.4">
      <rect x="83" y="-11" width="182" height="145" rx="3" />
      <path d="M97 14h51m-51 6h84M97 36h152M97 64h152M97 92h152" />
      {[47, 75, 103].map((y) => <g key={y}>
        <path d={`M97 ${y}h14`} />
        {[143, 166, 189, 212].map((x) => <circle key={x} cx={x} cy={y} r="6" />)}
      </g>)}
      <circle cx="166" cy="47" r="3.5" fill="currentColor" stroke="none" />
      <circle cx="189" cy="75" r="3.5" fill="currentColor" stroke="none" />
    </g>
  </svg>
}
