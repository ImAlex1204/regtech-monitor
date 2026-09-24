import { useEffect, useRef } from 'react'
import { daysUntil, parseDeadline } from '../derive'
import { areaLabel, type Lang, type Strings } from '../i18n'
import type { Announcement, Mode, Status } from '../types'
import { FrameworkBadge, RiskBadge, SourcePill, StatusSegmented } from './Badges'
import { fmtDate } from './AnnouncementList'

// 右側玻璃抽屜：完整摘要、建議行動（Plan）、框架與理由、可編輯的處理狀態（Track）
export default function DetailDrawer({ item, mode, lang, s, onClose, onStatus }: {
  item: Announcement | null
  mode: Mode
  lang: Lang
  s: Strings
  onClose: () => void
  onStatus: (url: string, status: Status) => void
}) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!item) return
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [item, onClose])

  const deadline = item ? parseDeadline(item.deadline) : null
  const passed = deadline != null && daysUntil(deadline, new Date()) < 0

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px] transition-opacity ${item ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={item?.title}
        className={`glass fixed top-0 right-0 z-40 flex h-full w-full max-w-xl flex-col !rounded-none border-y-0 border-r-0 bg-[#0b101a]/80 transition-transform duration-300 sm:!rounded-l-3xl ${
          item ? 'translate-x-0' : 'pointer-events-none translate-x-full'
        }`}
      >
        {item && (
          <>
            <header className="flex items-start gap-3 border-b border-line p-5">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-3">
                  <SourcePill source={item.source} />
                  <RiskBadge risk={item.risk_level} lang={lang} />
                  <span className="num">{fmtDate(item.published_date)}</span>
                  <span>·</span>
                  <span>{areaLabel(lang, item.business_area)}</span>
                </div>
                <h2 className="text-lg leading-snug font-semibold text-ink">{item.title}</h2>
              </div>
              <button ref={closeRef} onClick={onClose} aria-label={s.close}
                className="rounded-lg border border-line p-1.5 text-ink-2 hover:border-line-2 hover:text-ink">
                <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden><path d="m5 5 10 10M15 5 5 15" strokeLinecap="round" /></svg>
              </button>
            </header>

            <div className="flex-1 space-y-6 overflow-y-auto p-5">
              <section>
                <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-ink-3">{s.detailStatus}</h3>
                <StatusSegmented value={item.status} lang={lang} onChange={st => onStatus(item.url, st)} />
                <p className="mt-2 text-[11px] text-ink-3">{mode === 'local' ? s.modeLocalHint : s.modeDemoHint}</p>
              </section>

              <section className="rounded-xl border border-accent/25 bg-accent/[0.07] p-4">
                <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-accent">{s.detailAction}</h3>
                <p className="text-sm leading-relaxed text-ink">{item.action ?? '—'}</p>
              </section>

              <section>
                <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-ink-3">{s.detailSummary}</h3>
                <p className="text-sm leading-relaxed text-ink-2">{item.summary ?? '—'}</p>
              </section>

              <section>
                <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-ink-3">{s.detailFrameworks}</h3>
                {item.frameworks.length ? (
                  <ul className="space-y-2.5">
                    {item.frameworks.map(t => (
                      <li key={t.name}>
                        <FrameworkBadge name={t.name} />
                        {t.reason && <p className="mt-1 text-xs leading-relaxed text-ink-2">{t.reason}</p>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-ink-3">{s.detailFrameworksNone}</p>
                )}
              </section>

              <section className="flex items-baseline gap-2 text-sm">
                <span className="text-[11px] font-medium uppercase tracking-wider text-ink-3">{s.detailDeadline}</span>
                <span className={`num ${deadline && !passed ? 'text-risk-mid' : 'text-ink-3'}`}>
                  {deadline ? fmtDate(item.deadline) : s.detailNone}{passed && s.deadlinePassed}
                </span>
              </section>
            </div>

            <footer className="border-t border-line p-5">
              <a href={item.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl bg-accent/90 px-4 py-2 text-sm font-medium text-white hover:bg-accent">
                {s.detailLink} <span aria-hidden>↗</span>
              </a>
            </footer>
          </>
        )}
      </aside>
    </>
  )
}
