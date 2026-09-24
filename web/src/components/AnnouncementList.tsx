import { parseDeadline } from '../derive'
import { areaLabel, type Lang, type Strings } from '../i18n'
import type { Announcement } from '../types'
import { FrameworkBadge, RiskBadge, SourcePill, StatusBadge } from './Badges'

export const fmtDate = (iso: string | null) => (iso ? iso.slice(0, 10) : '—')

// 每列只放「一眼掃過」需要的欄位 + 截斷摘要（看得出分類依據）；完整內容、建議行動、狀態編輯在詳細面板
export default function AnnouncementList({ items, selected, onSelect, lang, s }: {
  items: Announcement[]
  selected: string | null
  onSelect: (url: string) => void
  lang: Lang
  s: Strings
}) {
  if (!items.length) return <p className="glass px-5 py-10 text-center text-sm text-ink-3">{s.listEmpty}</p>

  return (
    <div className="glass overflow-hidden">
      <div className="hidden grid-cols-[64px_78px_minmax(0,1.1fr)_92px_minmax(0,3fr)_minmax(0,1.2fr)_96px] gap-3 border-b border-line px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-ink-3 lg:grid">
        <span>{s.colSource}</span><span>{s.colRisk}</span><span>{s.colArea}</span><span>{s.colDate}</span>
        <span>{s.colTitle}</span><span>{s.colFrameworks}</span><span>{s.colStatus}</span>
      </div>
      <ul>
        {items.map(a => {
          const active = a.url === selected
          const deadline = parseDeadline(a.deadline)
          return (
            <li key={a.url} className="border-b border-line last:border-b-0">
              <button
                onClick={() => onSelect(a.url)}
                aria-current={active}
                className={`grid w-full grid-cols-1 gap-2 px-4 py-3 text-left transition-colors lg:grid-cols-[64px_78px_minmax(0,1.1fr)_92px_minmax(0,3fr)_minmax(0,1.2fr)_96px] lg:items-start lg:gap-3 ${
                  active ? 'bg-accent/[0.09]' : 'hover:bg-white/[0.03]'
                }`}
              >
                <div className="flex flex-wrap items-center gap-2 lg:contents">
                  <span className="lg:pt-0.5"><SourcePill source={a.source} /></span>
                  <span className="lg:pt-0.5"><RiskBadge risk={a.risk_level} lang={lang} /></span>
                  <span className="text-xs text-ink-2 lg:pt-1">{areaLabel(lang, a.business_area)}</span>
                  <span className="num text-xs text-ink-3 lg:pt-1">{fmtDate(a.published_date)}</span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink">{a.title}</div>
                  {a.summary && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-2">{a.summary}</p>}
                  {deadline && (
                    <span className="num mt-1.5 inline-block text-[11px] text-risk-mid">⏱ {s.detailDeadline} {fmtDate(a.deadline)}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1 lg:pt-0.5">
                  {a.frameworks.map(t => <FrameworkBadge key={t.name} name={t.name} title={t.reason ?? undefined} />)}
                </div>
                <span className="lg:pt-1"><StatusBadge status={a.status} lang={lang} /></span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
