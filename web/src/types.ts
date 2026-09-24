export type Source = 'FCA' | 'SEC'
export type Risk = '高' | '中' | '低'
export type Status = 'todo' | 'in_progress' | 'done' | 'na'

export const STATUSES: Status[] = ['todo', 'in_progress', 'done', 'na']
export const RISKS: Risk[] = ['高', '中', '低']

export interface FrameworkTag {
  name: string
  reason: string | null
}

// 跟 export_json.py / api.py 輸出的欄位一一對應
export interface Announcement {
  url: string
  title: string
  source: Source
  published_date: string | null
  summary: string | null
  business_area: string | null
  risk_level: Risk | null
  deadline: string | null
  frameworks: FrameworkTag[]
  action: string | null
  status: Status
}

export interface Dataset {
  last_fetched_at: string | null
  announcements: Announcement[]
}

// local：接到本機 api.py，狀態寫進 SQLite；demo：GitHub Pages 靜態版，狀態只存在這個瀏覽器
export type Mode = 'local' | 'demo'
