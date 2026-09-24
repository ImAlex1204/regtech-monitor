import { describe, expect, it } from 'vitest'
import {
  NO_FRAMEWORK, applyFilters, areaBreakdown, emptyFilters, parseDeadline, upcomingDeadlines, weekStart, weeklySeries,
} from './derive'
import type { Announcement } from './types'

const make = (over: Partial<Announcement>): Announcement => ({
  url: Math.random().toString(36),
  title: 'Title',
  source: 'FCA',
  published_date: '2026-09-16T10:00:00+00:00',
  summary: 'Summary',
  business_area: '洗錢防制與金融犯罪',
  risk_level: '中',
  deadline: null,
  frameworks: [],
  action: null,
  status: 'todo',
  ...over,
})

describe('parseDeadline', () => {
  it('accepts real YYYY-MM-DD dates', () => {
    expect(parseDeadline('2027-10-11')?.toISOString()).toBe('2027-10-11T00:00:00.000Z')
  })
  it('rejects relative descriptions the LLM sometimes returns', () => {
    expect(parseDeadline('60 days following publication in the Federal Register')).toBeNull()
  })
  it('rejects impossible calendar dates instead of rolling them over', () => {
    expect(parseDeadline('2026-02-30')).toBeNull()
  })
  it('handles null', () => {
    expect(parseDeadline(null)).toBeNull()
  })
})

describe('weekStart', () => {
  it('buckets to Monday (UTC)', () => {
    expect(weekStart('2026-09-20T23:00:00+00:00')?.toISOString().slice(0, 10)).toBe('2026-09-14')  // Sunday
    expect(weekStart('2026-09-21T00:30:00+00:00')?.toISOString().slice(0, 10)).toBe('2026-09-21')  // Monday
  })
})

describe('weeklySeries', () => {
  it('fills empty weeks with zero and counts high risk per source', () => {
    const series = weeklySeries([
      make({ published_date: '2026-09-01T00:00:00Z', risk_level: '高' }),
      make({ published_date: '2026-09-16T00:00:00Z', source: 'SEC' }),
    ])
    expect(series.map(p => p.week.toISOString().slice(0, 10))).toEqual(['2026-08-31', '2026-09-07', '2026-09-14'])
    expect(series[0].high.FCA).toBe(1)
    expect(series[1].total).toEqual({ FCA: 0, SEC: 0 })
    expect(series[2].total.SEC).toBe(1)
  })
})

describe('applyFilters', () => {
  const items = [
    make({ source: 'FCA', risk_level: '高', frameworks: [{ name: 'AML (MLRs / BSA)', reason: null }] }),
    make({ source: 'SEC', risk_level: '中', frameworks: [{ name: 'Exchange Act', reason: null }, { name: 'Securities Act', reason: null }] }),
    make({ source: 'SEC', risk_level: '低', frameworks: [], status: 'done', title: 'SEC names new COO' }),
  ]

  it('returns everything when no filter is set', () => {
    expect(applyFilters(items, emptyFilters())).toHaveLength(3)
  })
  it('ORs values within a group and ANDs across groups', () => {
    const f = emptyFilters()
    f.frameworks = new Set(['AML (MLRs / BSA)', 'Securities Act'])
    expect(applyFilters(items, f)).toHaveLength(2)
    f.sources = new Set(['SEC'])
    expect(applyFilters(items, f)).toHaveLength(1)
  })
  it('can select announcements without any framework tag', () => {
    const f = emptyFilters()
    f.frameworks = new Set([NO_FRAMEWORK])
    expect(applyFilters(items, f).map(a => a.title)).toEqual(['SEC names new COO'])
  })
  it('filters by status and free-text search', () => {
    const f = emptyFilters()
    f.statuses = new Set(['done'])
    expect(applyFilters(items, f)).toHaveLength(1)
    expect(applyFilters(items, { ...emptyFilters(), q: 'coo' })).toHaveLength(1)
  })
})

describe('upcomingDeadlines', () => {
  it('drops past and unparseable deadlines, groups by source, soonest first', () => {
    const today = new Date('2026-09-24T15:00:00Z')
    const list = upcomingDeadlines([
      make({ source: 'SEC', deadline: '2026-10-01' }),
      make({ source: 'FCA', deadline: '2027-01-01' }),
      make({ source: 'FCA', deadline: '2026-09-24' }),
      make({ source: 'FCA', deadline: '2023-11-13' }),
      make({ source: 'SEC', deadline: '60 days after publication' }),
    ], today)
    expect(list.map(u => [u.item.source, u.days])).toEqual([['FCA', 0], ['FCA', 99], ['SEC', 7]])
  })
})

describe('areaBreakdown', () => {
  it('sorts by total count, descending', () => {
    const rows = areaBreakdown([
      make({ business_area: 'A' }), make({ business_area: 'B', source: 'SEC' }), make({ business_area: 'B' }),
    ])
    expect(rows.map(r => [r.area, r.counts.FCA, r.counts.SEC])).toEqual([['B', 1, 1], ['A', 1, 0]])
  })
})
