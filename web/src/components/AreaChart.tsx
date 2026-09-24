import { useState } from 'react'
import type { AreaRow } from '../derive'
import { SOURCES } from '../derive'
import { areaLabel, type Lang } from '../i18n'
import { SOURCE_COLOR } from './Badges'

// 分組水平長條：每個業務範圍兩條（FCA / SEC），同一條刻度；類別名稱放在長條上方，手機寬度也不會被擠掉
export default function AreaChart({ title, rows, lang, onPick }: { title: string; rows: AreaRow[]; lang: Lang; onPick: (area: string) => void }) {
  const [hover, setHover] = useState<string | null>(null)
  const max = Math.max(1, ...rows.flatMap(r => SOURCES.map(src => r.counts[src])))

  return (
    <figure className="glass min-w-0 p-4">
      <figcaption className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink">{title}</span>
        <span className="flex items-center gap-3 text-xs text-ink-2">
          {SOURCES.map(src => (
            <span key={src} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: SOURCE_COLOR[src] }} aria-hidden />
              {src}
            </span>
          ))}
        </span>
      </figcaption>
      <ul className="space-y-2.5">
        {rows.map(r => {
          const active = hover === r.area
          return (
            <li key={r.area}>
              <button
                className={`block w-full rounded-lg px-2 py-1.5 text-left transition-colors ${active ? 'bg-white/[0.05]' : ''}`}
                onPointerEnter={() => setHover(r.area)}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover(r.area)}
                onBlur={() => setHover(null)}
                onClick={() => onPick(r.area)}
                title={areaLabel(lang, r.area)}
              >
                <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
                  <span className="truncate text-ink-2">{areaLabel(lang, r.area)}</span>
                  <span className="num shrink-0 text-ink-3">
                    {active ? SOURCES.map(src => `${src} ${r.counts[src]}`).join(' · ') : r.total}
                  </span>
                </div>
                <div className="space-y-[2px]">
                  {SOURCES.map(src => (
                    <div key={src} className="h-[7px]">
                      {r.counts[src] > 0 && (
                        <div
                          className="h-full rounded-r-[4px] transition-[width] duration-300"
                          style={{ width: `${(r.counts[src] / max) * 100}%`, minWidth: 4, background: SOURCE_COLOR[src], opacity: hover && !active ? 0.45 : 1 }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}
