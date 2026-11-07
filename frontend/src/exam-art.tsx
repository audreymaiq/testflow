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
