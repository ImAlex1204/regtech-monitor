import { useState } from 'react'
import { NO_FRAMEWORK, SOURCES, isFiltered, type Filters } from '../derive'
import { RISK_LABEL, STATUS_LABEL, areaLabel, type Lang, type Strings } from '../i18n'
import { RISKS, STATUSES } from '../types'
import { SOURCE_COLOR } from './Badges'

type SetKey = 'sources' | 'risks' | 'areas' | 'frameworks' | 'statuses'

function ChipGroup<T extends string>({ label, options, selected, format, count, onToggle, dot }: {
  label: string
  options: T[]
  selected: Set<T>
  format: (v: T) => string
  count: (v: T) => number
  onToggle: (v: T) => void
  dot?: (v: T) => string | undefined
}) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
      <span className="w-24 shrink-0 pt-1 text-[11px] font-medium uppercase tracking-wider text-ink-3">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {options.map(v => (
          <button key={v} className="chip" aria-pressed={selected.has(v)} onClick={() => onToggle(v)}>
            {dot?.(v) && <span className="h-2 w-2 rounded-full" style={{ background: dot(v) }} aria-hidden />}
            {format(v)}
            <span className="num text-[10px] text-ink-3">{count(v)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// 所有篩選器用同一套 chip 互動：沒選任何值 = 全部；同一組內多選是「或」，不同組之間是「且」
export default function FilterBar({ filters, setFilters, areas, frameworks, counts, lang, s }: {
  filters: Filters
  setFilters: (f: Filters) => void
  areas: string[]
  frameworks: string[]
  counts: { [K in SetKey]: (v: string) => number }
  lang: Lang
  s: Strings
}) {
  const [open, setOpen] = useState(false)

  const toggle = (key: SetKey, v: string) => {
    const next = new Set(filters[key] as Set<string>)
    if (next.has(v)) next.delete(v)
    else next.add(v)
    setFilters({ ...filters, [key]: next })
  }

  return (
    <section className="glass p-4" aria-label={s.filters}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-52 flex-1">
          <svg className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-ink-3" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" strokeLinecap="round" />
          </svg>
          <input
            value={filters.q}
            onChange={e => setFilters({ ...filters, q: e.target.value })}
            placeholder={s.search}
            aria-label={s.search}
            className="w-full rounded-xl border border-line bg-black/20 py-2 pr-3 pl-9 text-sm text-ink placeholder:text-ink-3 focus:border-accent/60 focus:outline-none"
          />
        </div>
        <button className="chip sm:hidden" aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {s.filters} {open ? '▴' : '▾'}
        </button>
        {isFiltered(filters) && (
          <button
            className="text-xs text-accent hover:underline"
            onClick={() => setFilters({ sources: new Set(), risks: new Set(), areas: new Set(), frameworks: new Set(), statuses: new Set(), q: '' })}
          >
            {s.reset}
          </button>
        )}
      </div>
      <div className={`mt-4 space-y-3 ${open ? '' : 'hidden sm:block'}`}>
        <ChipGroup label={s.filterSource} options={SOURCES} selected={filters.sources} format={v => v}
          count={counts.sources} onToggle={v => toggle('sources', v)} dot={v => SOURCE_COLOR[v]} />
        <ChipGroup label={s.filterRisk} options={RISKS} selected={filters.risks} format={v => RISK_LABEL[lang][v]}
          count={counts.risks} onToggle={v => toggle('risks', v)} />
        <ChipGroup label={s.filterStatus} options={STATUSES} selected={filters.statuses} format={v => STATUS_LABEL[lang][v]}
          count={counts.statuses} onToggle={v => toggle('statuses', v)} />
        <ChipGroup label={s.filterFramework} options={[...frameworks, NO_FRAMEWORK]} selected={filters.frameworks}
          format={v => (v === NO_FRAMEWORK ? s.noFramework : v)} count={counts.frameworks} onToggle={v => toggle('frameworks', v)} />
        <ChipGroup label={s.filterArea} options={areas} selected={filters.areas} format={v => areaLabel(lang, v)}
          count={counts.areas} onToggle={v => toggle('areas', v)} />
      </div>
    </section>
  )
}
