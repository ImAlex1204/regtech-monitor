import { useLayoutEffect, useRef, useState } from 'react'
import type { WeekPoint } from '../derive'
import { SOURCES } from '../derive'
import type { Strings } from '../i18n'
import type { Source } from '../types'
import { SOURCE_COLOR } from './Badges'

const H = 200
const PAD = { top: 12, right: 44, bottom: 24, left: 28 }

const fmtWeek = (d: Date) => d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' })

// 上限取偶數倍，中間那條刻度（yMax / 2）才會是整數，公告數不會出現 7.5 這種刻度
function niceMax(v: number) {
  if (v <= 4) return 4
  const step = v <= 10 ? 2 : v <= 20 ? 4 : 10
  return Math.ceil(v / step) * step
}

// 兩條線（FCA / SEC）共用同一個 y 軸；圖例常駐 + 最後一點直接標註機構名稱，身分不單靠顏色
export default function TrendChart({ title, points, metric, s }: { title: string; points: WeekPoint[]; metric: 'total' | 'high'; s: Strings }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(320)
  const [hover, setHover] = useState<number | null>(null)

  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(260, e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const values = points.flatMap(p => SOURCES.map(src => p[metric][src]))
  const yMax = niceMax(Math.max(0, ...values))
  const x = (i: number) => PAD.left + (points.length <= 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH
  const ticks = [0, yMax / 2, yMax]
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(innerW / 70))))

  // 每個機構從「第一筆有資料的那週」才開始畫：之前的空白是還沒開始追蹤，不是那幾週真的沒有公告，
  // 畫成 0 會誤導（FCA 的 RSS 只保留最近的公告，資料起點比 SEC 晚）
  const firstIdx = (src: Source) => points.findIndex(p => p.total[src] > 0)
  const path = (src: Source) => {
    const start = firstIdx(src)
    if (start < 0) return ''
    return points.slice(start).map((p, i) => `${i ? 'L' : 'M'}${x(start + i).toFixed(1)},${y(p[metric][src]).toFixed(1)}`).join(' ')
  }
  const tracked = (src: Source, i: number) => { const f = firstIdx(src); return f >= 0 && i >= f }

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    if (!points.length) return
    const rect = e.currentTarget.getBoundingClientRect()
    const rel = (e.clientX - rect.left) / rect.width
    setHover(Math.min(points.length - 1, Math.max(0, Math.round(rel * (points.length - 1)))))
  }

  const hp = hover != null ? points[hover] : null
  const last = points.length - 1
  // 線尾的直接標註：兩個機構數值接近時上下推開，避免文字疊在一起
  const endY: Record<Source, number> = { FCA: 0, SEC: 0 }
  if (last >= 0) {
    const [a, b] = [...SOURCES].sort((p, q) => y(points[last][metric][p]) - y(points[last][metric][q]))
    endY[a] = y(points[last][metric][a])
    endY[b] = Math.max(y(points[last][metric][b]), endY[a] + 12)
  }

  return (
    <figure className="glass relative min-w-0 p-4">
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink">{title}</span>
        <span className="flex items-center gap-3 text-xs text-ink-2">
          {SOURCES.map(src => (
            <span key={src} className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-3.5 rounded-full" style={{ background: SOURCE_COLOR[src] }} aria-hidden />
              {src}
            </span>
          ))}
        </span>
      </figcaption>
      <div ref={wrapRef} className="relative">
        <svg width="100%" height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label={title} className="block overflow-visible">
          {ticks.map(t => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="rgba(255,255,255,0.07)" strokeDasharray={t === 0 ? undefined : '3 4'} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-3 text-[10px]">{t}</text>
            </g>
          ))}
          {points.map((p, i) => i % labelEvery === 0 && (
            <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="num fill-ink-3 text-[10px]">{fmtWeek(p.week)}</text>
          ))}
          {hp && <line x1={x(hover!)} x2={x(hover!)} y1={PAD.top} y2={PAD.top + innerH} stroke="rgba(255,255,255,0.25)" />}
          {SOURCES.map(src => (
            <g key={src}>
              <path d={path(src)} fill="none" stroke={SOURCE_COLOR[src]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {last >= 0 && (
                <text x={x(last) + 8} y={endY[src]} dy="0.32em" className="num fill-ink-2 text-[10px]">{src}</text>
              )}
              {hp && tracked(src, hover!) && (
                <circle cx={x(hover!)} cy={y(hp[metric][src])} r={4} fill={SOURCE_COLOR[src]} stroke="#0b0f18" strokeWidth={2} />
              )}
            </g>
          ))}
          <rect
            x={PAD.left} y={PAD.top} width={innerW} height={innerH} fill="transparent"
            onPointerMove={onMove} onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hp && (
          <div
            className="pointer-events-none absolute top-1 z-10 min-w-32 rounded-lg border border-line-2 bg-[#0d121c]/95 px-3 py-2 text-xs shadow-xl"
            style={x(hover!) > width / 2 ? { right: width - x(hover!) + 10 } : { left: x(hover!) + 10 }}
          >
            <div className="mb-1 text-ink-3">{s.weekOf} {fmtWeek(hp.week)}</div>
            {SOURCES.map(src => (
              <div key={src} className="flex items-center justify-between gap-4">
                <span className="inline-flex items-center gap-1.5 text-ink-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLOR[src] }} aria-hidden />{src}
                </span>
                <span className="num text-ink">{tracked(src, hover!) ? hp[metric][src] : '—'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </figure>
  )
}
