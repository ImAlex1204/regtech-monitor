import { RISK_LABEL, STATUS_LABEL, type Lang } from '../i18n'
import { STATUSES, type Risk, type Source, type Status } from '../types'

export const SOURCE_COLOR: Record<Source, string> = { FCA: 'var(--color-fca)', SEC: 'var(--color-sec)' }

export function SourcePill({ source }: { source: Source }) {
  return (
    <span className="num inline-flex items-center gap-1.5 rounded-md border border-line bg-white/[0.03] px-1.5 py-0.5 text-[11px] font-medium text-ink">
      <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLOR[source] }} aria-hidden />
      {source}
    </span>
  )
}

// 風險等級：狀態色 + 形狀 + 文字，三者一起出現，色覺辨識障礙者也不會只靠顏色判斷
const RISK_STYLE: Record<Risk, { icon: string; cls: string }> = {
  高: { icon: '▲', cls: 'text-risk-high bg-risk-high/12 border-risk-high/30' },
  中: { icon: '◆', cls: 'text-risk-mid bg-risk-mid/10 border-risk-mid/25' },
  低: { icon: '●', cls: 'text-risk-low bg-white/[0.04] border-line' },
}

export function RiskBadge({ risk, lang }: { risk: Risk | null; lang: Lang }) {
  if (!risk) return <span className="text-ink-3">—</span>
  const s = RISK_STYLE[risk]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-semibold ${s.cls}`}>
      <span aria-hidden className="text-[9px]">{s.icon}</span>
      {RISK_LABEL[lang][risk]}
    </span>
  )
}

export function FrameworkBadge({ name, title }: { name: string; title?: string }) {
  return (
    <span title={title} className="inline-flex whitespace-nowrap rounded-md border border-violet-300/20 bg-violet-400/10 px-1.5 py-0.5 text-[11px] font-medium text-violet-200">
      {name}
    </span>
  )
}

const STATUS_STYLE: Record<Status, { icon: string; cls: string }> = {
  todo: { icon: '○', cls: 'text-ink-2' },
  in_progress: { icon: '◐', cls: 'text-sky-300' },
  done: { icon: '✓', cls: 'text-emerald-300' },
  na: { icon: '–', cls: 'text-ink-3' },
}

export function StatusBadge({ status, lang }: { status: Status; lang: Lang }) {
  const s = STATUS_STYLE[status]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap text-xs ${s.cls}`}>
      <span aria-hidden>{s.icon}</span>
      {STATUS_LABEL[lang][status]}
    </span>
  )
}

// 分段式狀態切換（詳細面板裡用）
export function StatusSegmented({ value, lang, onChange }: { value: Status; lang: Lang; onChange: (s: Status) => void }) {
  return (
    <div role="radiogroup" className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
      {STATUSES.map(s => {
        const active = s === value
        return (
          <button
            key={s}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(s)}
            className={`rounded-lg border px-2 py-2 text-xs transition-colors ${
              active ? 'border-accent/60 bg-accent/15 text-ink' : 'border-line bg-white/[0.02] text-ink-2 hover:border-line-2 hover:text-ink'
            }`}
          >
            <span className={`mr-1 ${STATUS_STYLE[s].cls}`} aria-hidden>{STATUS_STYLE[s].icon}</span>
            {STATUS_LABEL[lang][s]}
          </button>
        )
      })}
    </div>
  )
}
