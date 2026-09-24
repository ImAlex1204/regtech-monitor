"""本機 API（Track 的 A 方案）：前端在本機接到這支 API 時，處理狀態直接寫進 SQLite，真正持久。

    uvicorn api:app --port 8000            # 然後開 http://127.0.0.1:8000
    （開發前端時：cd web && npm run dev，Vite 會把 /api 轉到這裡）

GitHub Pages 上的線上版沒有這支 API，前端會自動退回 Demo 模式（狀態只存在瀏覽器）。
只綁 127.0.0.1、沒有登入機制，本來就只打算給自己在本機用，不要部署到公開網路上。
"""
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from export_json import load_payload
from pipeline import STATUSES, get_connection

app = FastAPI(title="RegTech Monitor local API")


class StatusUpdate(BaseModel):
    url: str
    status: Literal[STATUSES]


@app.get("/api/announcements")
def announcements() -> dict:
    return load_payload()


@app.patch("/api/announcements/status")
def update_status(body: StatusUpdate) -> dict:
    conn = get_connection()
    cur = conn.execute("UPDATE announcements SET status = ? WHERE url = ?", (body.status, body.url))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="announcement not found")
    return {"url": body.url, "status": body.status}


# 有 build 過前端（web/dist）就一起提供，本機只要開這一個服務
WEB_DIST = Path(__file__).parent / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
