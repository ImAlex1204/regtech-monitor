import type { Dataset, Mode, Status } from './types'

// Track 的 A+B 方案：
//   A（本機）：前端接到 api.py 時，狀態寫進 SQLite，是真正持久的處理紀錄
//   B（Demo）：GitHub Pages 靜態版沒有伺服器，狀態疊加在 localStorage，只存在這個瀏覽器
const DEMO_KEY = 'regtech-status-overrides'

function readOverrides(): Record<string, Status> {
  try {
    return JSON.parse(localStorage.getItem(DEMO_KEY) ?? '{}')
  } catch {
    return {}
  }
}

export async function loadDataset(): Promise<{ data: Dataset; mode: Mode }> {
  try {
    const res = await fetch('api/announcements', { headers: { Accept: 'application/json' } })
    // GitHub Pages 找不到路徑時會回 404 HTML，所以要確認真的是 JSON 才算本機模式
    if (res.ok && res.headers.get('content-type')?.includes('application/json')) {
      return { data: await res.json(), mode: 'local' }
    }
  } catch {
    // 沒有本機 API，退回 Demo 模式
  }
  const res = await fetch('data/announcements.json')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data: Dataset = await res.json()
  const overrides = readOverrides()
  for (const a of data.announcements) {
    const s = overrides[a.url]
    if (s) a.status = s
  }
  return { data, mode: 'demo' }
}

export async function saveStatus(mode: Mode, url: string, status: Status): Promise<void> {
  if (mode === 'local') {
    const res = await fetch('api/announcements/status', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, status }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return
  }
  try {
    const overrides = readOverrides()
    overrides[url] = status
    localStorage.setItem(DEMO_KEY, JSON.stringify(overrides))
  } catch {
    // 無痕模式或封鎖儲存時寫不進去：這次瀏覽仍保留在畫面狀態裡，只是重新整理後會消失
  }
}
