type DeckMarkProps = { title: string; icon: string; color: string }

export function DeckMark({ title, icon, color }: DeckMarkProps) {
  const legacyEye = icon.replace(/\uFE0F/g, '') === '\u{1F441}'
  return <span className="home-deck-mark" aria-hidden="true"
    style={/^#[0-9a-fA-F]{6}$/.test(color) ? { borderColor: color } : undefined}>
    {legacyEye ? <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M3 16c3.5-5 7.8-7.5 13-7.5S25.5 11 29 16c-3.5 5-7.8 7.5-13 7.5S6.5 21 3 16Z" />
      <circle cx="16" cy="16" r="3.5" />
    </svg> : title.trim().slice(0, 2).toLocaleUpperCase('vi-VN')}
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
