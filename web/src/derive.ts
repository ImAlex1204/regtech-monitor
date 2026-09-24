// 純邏輯（篩選、週彙總、期限解析），不碰 React，才能直接寫單元測試（derive.test.ts）
import type { Announcement, Risk, Source, Status } from './types'

export const SOURCES: Source[] = ['FCA', 'SEC']
export const NO_FRAMEWORK = '__none__'

// 每個維度的「已選」集合；空集合代表不篩這個維度（= 全部）
export interface Filters {
  sources: Set<Source>
  risks: Set<Risk>
  areas: Set<string>
  frameworks: Set<string>  // 框架名稱，或 NO_FRAMEWORK 代表「沒有任何框架標籤」
  statuses: Set<Status>
  q: string
}

export const emptyFilters = (): Filters => ({
  sources: new Set(), risks: new Set(), areas: new Set(), frameworks: new Set(), statuses: new Set(), q: '',
})

export const isFiltered = (f: Filters) =>
  f.sources.size + f.risks.size + f.areas.size + f.frameworks.size + f.statuses.size > 0 || f.q.trim() !== ''

export function applyFilters(items: Announcement[], f: Filters): Announcement[] {
  const q = f.q.trim().toLowerCase()
  return items.filter(a => {
    if (f.sources.size && !f.sources.has(a.source)) return false
    if (f.risks.size && !(a.risk_level && f.risks.has(a.risk_level))) return false
    if (f.areas.size && !(a.business_area && f.areas.has(a.business_area))) return false
    if (f.statuses.size && !f.statuses.has(a.status)) return false
    if (f.frameworks.size) {
      // 多選框架是「任一符合」：公告只要帶有其中一個被選的框架就留下
      const names = a.frameworks.map(t => t.name)
      const hit = names.some(n => f.frameworks.has(n)) || (names.length === 0 && f.frameworks.has(NO_FRAMEWORK))
      if (!hit) return false
    }
    if (q && !`${a.title} ${a.summary ?? ''}`.toLowerCase().includes(q)) return false
    return true
  })
}

// deadline 由 LLM 產生，偶爾不遵守「只給 YYYY-MM-DD」的指示（例如 "60 days following publication..."）。
// 只接受能解析成真實日期的值，其他一律當作沒有期限，不把原始字串顯示給使用者。
export function parseDeadline(raw: string | null): Date | null {
  if (!raw || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null
  const d = new Date(`${raw}T00:00:00Z`)
  return Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== raw ? null : d
}

const DAY = 86_400_000
export const utcMidnight = (d: Date) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
export const daysUntil = (deadline: Date, today: Date) => Math.round((deadline.getTime() - utcMidnight(today).getTime()) / DAY)

// 週一為一週的開始（UTC）
export function weekStart(iso: string): Date | null {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const day = utcMidnight(d)
  const offset = (day.getUTCDay() + 6) % 7
  return new Date(day.getTime() - offset * DAY)
}

export interface WeekPoint {
  week: Date
  total: Record<Source, number>
  high: Record<Source, number>
}

// 每週彙總。中間沒有公告的週也補 0，折線才不會把空白週直接連過去、誤導成「持續有量」
export function weeklySeries(items: Announcement[]): WeekPoint[] {
  const buckets = new Map<number, WeekPoint>()
  for (const a of items) {
    const w = a.published_date ? weekStart(a.published_date) : null
    if (!w) continue
    const key = w.getTime()
    const p = buckets.get(key) ?? { week: w, total: { FCA: 0, SEC: 0 }, high: { FCA: 0, SEC: 0 } }
    p.total[a.source] += 1
    if (a.risk_level === '高') p.high[a.source] += 1
    buckets.set(key, p)
  }
  if (buckets.size === 0) return []
  const keys = [...buckets.keys()].sort((x, y) => x - y)
  const out: WeekPoint[] = []
  for (let k = keys[0]; k <= keys[keys.length - 1]; k += 7 * DAY) {
    out.push(buckets.get(k) ?? { week: new Date(k), total: { FCA: 0, SEC: 0 }, high: { FCA: 0, SEC: 0 } })
  }
  return out
}

export interface AreaRow {
  area: string
  counts: Record<Source, number>
  total: number
}

export function areaBreakdown(items: Announcement[]): AreaRow[] {
  const rows = new Map<string, AreaRow>()
  for (const a of items) {
    if (!a.business_area) continue
    const r = rows.get(a.business_area) ?? { area: a.business_area, counts: { FCA: 0, SEC: 0 }, total: 0 }
    r.counts[a.source] += 1
    r.total += 1
    rows.set(a.business_area, r)
  }
  return [...rows.values()].sort((x, y) => y.total - x.total || x.area.localeCompare(y.area))
}

export interface Upcoming {
  item: Announcement
  deadline: Date
  days: number
}

// 依機構分組、組內最近到期排前面（跟原本 Streamlit 版一致：先看得出兩個機構的分界）
export function upcomingDeadlines(items: Announcement[], today: Date): Upcoming[] {
  const out: Upcoming[] = []
  for (const item of items) {
    const deadline = parseDeadline(item.deadline)
    if (!deadline) continue
    const days = daysUntil(deadline, today)
    if (days >= 0) out.push({ item, deadline, days })
  }
  return out.sort((x, y) => x.item.source.localeCompare(y.item.source) || x.days - y.days)
}

export const sortForList = (items: Announcement[]) =>
  [...items].sort((x, y) => x.source.localeCompare(y.source) || (y.published_date ?? '').localeCompare(x.published_date ?? ''))

export const frameworkNames = (items: Announcement[]) =>
  [...new Set(items.flatMap(a => a.frameworks.map(t => t.name)))].sort()
