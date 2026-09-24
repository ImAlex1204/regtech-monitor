import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadDataset, saveStatus } from './api'
import {
  SOURCES, applyFilters, areaBreakdown, emptyFilters, frameworkNames, parseDeadline,
  sortForList, upcomingDeadlines, weeklySeries, type Filters,
} from './derive'
import { TEXT, areaLabel, type Lang, type Strings } from './i18n'
import type { Announcement, Mode, Source, Status } from './types'
import AnnouncementList, { fmtDate } from './components/AnnouncementList'
import AreaChart from './components/AreaChart'
import { RiskBadge, SOURCE_COLOR, SourcePill } from './components/Badges'
import DetailDrawer from './components/DetailDrawer'
import FilterBar from './components/FilterBar'
import TrendChart from './components/TrendChart'

function readLang(): Lang {
  // ?lang=en 可以直接分享英文版連結；沒有指定時沿用上次的選擇
  const param = new URLSearchParams(window.location.search).get('lang')
  if (param === 'zh' || param === 'en') return param
  try {
    const v = localStorage.getItem('lang')
    if (v === 'zh' || v === 'en') return v
  } catch { /* 儲存被封鎖時用預設語言 */ }
  return 'zh'
}

function TopBar({ s, lang, setLang, mode, updated }: { s: Strings; lang: Lang; setLang: (l: Lang) => void; mode: Mode | null; updated: string | null }) {
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-3">
      <div className="flex items-center gap-3">
        <div className="relative grid h-10 w-10 place-items-center rounded-xl border border-line-2 bg-white/[0.04]" aria-hidden>
          <span className="absolute h-6 w-6 rounded-full border-2 border-fca/80" />
          <span className="h-2 w-2 rounded-full bg-sec shadow-[0_0_12px_#d95926]" />
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">{s.title}</h1>
          <p className="text-xs text-ink-3">{s.subtitle}</p>
        </div>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-ink-3">
        {updated && <span className="num">{s.updated} {updated.slice(0, 16).replace('T', ' ')} UTC</span>}
        {mode && (
          <span title={mode === 'local' ? s.modeLocalHint : s.modeDemoHint}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${mode === 'local' ? 'border-emerald-400/30 text-emerald-300' : 'border-amber-300/30 text-amber-200'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${mode === 'local' ? 'bg-emerald-400' : 'bg-amber-300'}`} />
            {mode === 'local' ? s.modeLocal : s.modeDemo}
          </span>
        )}
        <button className="chip" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>{lang === 'zh' ? 'EN' : '繁中'}</button>
      </div>
    </header>
  )
}

// 每張 KPI 卡：總數 + FCA / SEC 拆分（雙機構比較指標）
function Kpi({ label, bySource, accent }: { label: string; bySource: Record<Source, number>; accent?: string }) {
  const total = bySource.FCA + bySource.SEC
  return (
    <div className="glass p-4">
      <div className="text-[11px] font-medium uppercase tracking-wider text-ink-3">{label}</div>
      <div className={`num mt-1 text-3xl font-semibold ${accent ?? 'text-ink'}`}>{total}</div>
      <div className="mt-3 flex h-1.5 gap-[2px] overflow-hidden rounded-full bg-white/[0.05]">
        {SOURCES.map(src => bySource[src] > 0 && (
          <div key={src} style={{ flexGrow: bySource[src], background: SOURCE_COLOR[src] }} />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs">
        {SOURCES.map(src => (
          <span key={src} className="inline-flex items-center gap-1.5 text-ink-2">
            <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLOR[src] }} aria-hidden />
            {src} <span className={`num text-ink ${src === 'FCA' ? 'glow-fca' : 'glow-sec'}`}>{bySource[src]}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

const countBy = (items: Announcement[], pred: (a: Announcement) => boolean) => ({
  FCA: items.filter(a => a.source === 'FCA' && pred(a)).length,
  SEC: items.filter(a => a.source === 'SEC' && pred(a)).length,
})

export default function App() {
  const [lang, setLangState] = useState<Lang>(readLang)
  const [items, setItems] = useState<Announcement[] | null>(null)
  const [updated, setUpdated] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [selected, setSelected] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const s = TEXT[lang]

  const setLang = (l: Lang) => {
    setLangState(l)
    try { localStorage.setItem('lang', l) } catch { /* 忽略 */ }
  }

  useEffect(() => { document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : 'en' }, [lang])

  useEffect(() => {
    loadDataset()
      .then(({ data, mode }) => { setItems(data.announcements); setUpdated(data.last_fetched_at); setMode(mode) })
      .catch(e => setError(String(e)))
  }, [])

  const all = items ?? []
  const filtered = useMemo(() => applyFilters(all, filters), [all, filters])
  const listItems = useMemo(() => sortForList(filtered), [filtered])
  const weekly = useMemo(() => weeklySeries(filtered), [filtered])
  const areas = useMemo(() => areaBreakdown(filtered), [filtered])
  const upcoming = useMemo(() => upcomingDeadlines(filtered, new Date()), [filtered])
  const areaOptions = useMemo(() => areaBreakdown(all).map(r => r.area), [all])
  const frameworkOptions = useMemo(() => frameworkNames(all), [all])

  // 每個選項旁的數字 = 「只選這個值、其他組維持現狀」會剩幾筆，點下去之前就知道結果
  const facet = (key: 'sources' | 'risks' | 'areas' | 'frameworks' | 'statuses') => (v: string) =>
    applyFilters(all, { ...filters, [key]: new Set([v]) } as Filters).length
  const counts = { sources: facet('sources'), risks: facet('risks'), areas: facet('areas'), frameworks: facet('frameworks'), statuses: facet('statuses') }

  const selectedItem = all.find(a => a.url === selected) ?? null
  const closeDrawer = useCallback(() => setSelected(null), [])

  const onStatus = async (url: string, status: Status) => {
    const prev = all.find(a => a.url === url)?.status
    if (!prev || !mode || prev === status) return
    setItems(list => list && list.map(a => (a.url === url ? { ...a, status } : a)))  // 先更新畫面，失敗再還原
    try {
      await saveStatus(mode, url, status)
    } catch {
      setItems(list => list && list.map(a => (a.url === url ? { ...a, status: prev } : a)))
      setToast(s.statusSaveError)
      setTimeout(() => setToast(null), 3500)
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-4 py-5 sm:px-6 lg:py-8">
      <TopBar s={s} lang={lang} setLang={setLang} mode={mode} updated={updated} />

      {error && <p className="glass p-6 text-sm text-risk-high">{s.loadError}: {error}</p>}
      {!items && !error && <p className="glass p-6 text-sm text-ink-3">{s.loading}</p>}

      {items && (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi label={s.kpiTotal} bySource={countBy(filtered, () => true)} />
            <Kpi label={s.kpiHigh} bySource={countBy(filtered, a => a.risk_level === '高')} accent="text-risk-high" />
            <Kpi label={s.kpiDeadline} bySource={countBy(filtered, a => parseDeadline(a.deadline) != null)} accent="text-risk-mid" />
            <Kpi label={s.kpiOpen} bySource={countBy(filtered, a => a.status === 'todo' || a.status === 'in_progress')} accent="text-accent" />
          </section>

          <FilterBar filters={filters} setFilters={setFilters} areas={areaOptions} frameworks={frameworkOptions}
            counts={counts} lang={lang} s={s} />

          <section className="space-y-3">
            <h2 className="px-1 text-sm font-medium text-ink-2">{s.trendsHeader}</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              <TrendChart title={s.chartWeekly} points={weekly} metric="total" s={s} />
              <TrendChart title={s.chartWeeklyHigh} points={weekly} metric="high" s={s} />
            </div>
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
              <AreaChart title={s.chartArea} rows={areas} lang={lang}
                onPick={area => setFilters({ ...filters, areas: new Set([area]) })} />
              <div className="glass p-4">
                <div className="mb-3 text-sm font-medium text-ink">{s.deadlinesHeader}</div>
                {upcoming.length === 0 ? (
                  <p className="py-6 text-center text-xs text-ink-3">{s.deadlinesEmpty}</p>
                ) : (
                  <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                    {upcoming.map(({ item, days }) => (
                      <li key={item.url}>
                        <button onClick={() => setSelected(item.url)}
                          className="flex w-full items-start gap-3 rounded-xl border border-line bg-white/[0.02] p-3 text-left hover:border-line-2 hover:bg-white/[0.04]">
                          <div className="w-[76px] shrink-0 text-center whitespace-nowrap">
                            <div className={`num text-sm font-semibold ${days <= 30 ? 'text-risk-high' : 'text-risk-mid'}`}>{s.daysLeft(days)}</div>
                            <div className="num text-[10px] text-ink-3">{fmtDate(item.deadline)}</div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="mb-1 flex flex-wrap items-center gap-1.5">
                              <SourcePill source={item.source} />
                              <RiskBadge risk={item.risk_level} lang={lang} />
                              <span className="truncate text-[11px] text-ink-3">{areaLabel(lang, item.business_area)}</span>
                            </div>
                            <div className="line-clamp-2 text-xs text-ink">{item.title}</div>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="px-1 text-sm font-medium text-ink-2">{s.listHeader(listItems.length)}</h2>
            <AnnouncementList items={listItems} selected={selected} onSelect={setSelected} lang={lang} s={s} />
          </section>

          <p className="px-1 pb-4 text-center text-[11px] text-ink-3">{s.footer}</p>
        </>
      )}

      <DetailDrawer item={selectedItem} mode={mode ?? 'demo'} lang={lang} s={s} onClose={closeDrawer} onStatus={onStatus} />

      {toast && (
        <div role="status" className="glass fixed bottom-5 left-1/2 z-50 -translate-x-1/2 px-4 py-2.5 text-sm text-risk-high">{toast}</div>
      )}
    </div>
  )
}

