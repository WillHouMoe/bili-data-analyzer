# BiliDataAnalyzer

一個用來解讀 Bilibili 創作者影片表現的儀表板：某段時間內發布了什麼、表現如何，以及這些數字如何累積。

<p>
  <a href="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml"><img src="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/WillHouMoe/bili-data-analyzer" alt="License: MIT"></a>
</p>

[English](README.md) · **繁體中文**

Bilibili 的創作中心只給你看自己帳號的總數和幾條趨勢線。BiliDataAnalyzer 能跨一位創作者近期的作品回答更廣的問題：哪些影片表現最好、發布節奏與影片時長跟關注度有什麼關係，以及互動如何隨時間累積。它吃任何公開的 UID，所以創作者回顧自己、粉絲或分析者研究別人、或是拿兩位創作者互相比較，都用得上。

給它一個 UID 和一段日期範圍，它就會抓出創作者在那段時間內發布的每一支影片，把表現數據畫成圖表。

留言、彈幕與字幕正文刻意不在範圍內。應用程式會保留 Bilibili 影片統計資料提供的留言與彈幕「數量」，但不會抓取或儲存底層正文。

![儀表板](docs/images/dashboard.png)

## 快速開始

需要 Docker 和 Docker Compose。

```bash
git clone https://github.com/WillHouMoe/bili-data-analyzer.git
cd bili-data-analyzer
./bilia start
```

這會在背景啟動應用程式，第一次執行時自動從範例建立 `.env`。之後用 `./bilia open` 開啟；需要時可用 `./bilia status` 與 `./bilia logs`。API 文件在與 UI 相同 port 的 `/docs`。

在 macOS 上執行一次 `./bilia install-login`，登入系統時會自動啟動 Docker 與分析服務；之後每五分鐘還會檢查並在需要時重啟容器。`./bilia uninstall-login` 可移除。啟動輸出位於 `/tmp/bilianalyzer-background.log`。`./bilia stop` 與 `./bilia down` 會先在本次登入階段卸載啟動器，避免手動停止後五分鐘又被拉起來。

抓取在伺服器行程中執行。送出抓取後可以直接關閉瀏覽器；之後打開儀表板只會讀取已儲存的結果，不會重新抓取。容器若在抓取途中重啟，未完成的批次會續跑並跳過已寫入的影片。

### 立刻看到有資料的畫面

抓一個真實創作者的資料需要一段時間，而且必須有 `SESSDATA` cookie。想在沒有 cookie 的情況下讓每個面板都有像樣的資料，可以：

```bash
docker compose exec app python -m scripts.seed_demo
```

這會產生一個虛構創作者，附帶幾個月份的影片中繼資料與表現數據。加上 `--reset` 可以重新開始。

## 開始使用

1. **Add creator** —— 輸入創作者的 UID（就是 `space.bilibili.com/546195` 裡的那個數字），選一段日期範圍。側邊欄會顯示抓取進度。
2. **Dashboard** —— 摘要卡片、觀看數趨勢、互動數比較、觀看數對互動率散佈圖、時長分析與發布節奏。目錄現在以 UP 主為單位，單次抓取只是其下的批次；帳號總粉絲、總播放與總獲讚由 Bilibili 的 UP 主統計接口取得。影片績效快照只更新最近 30–50 支作品，粉絲、帳號播放與帳號獲讚歷史則另存為 UP 主快照，並以兩張並排圖表呈現：左側是粉絲，右側是帳號播放與獲讚。
3. **Video detail** —— 單支影片的數據，附雷達圖，以及跟這位 UP 主合併作品庫平均值的差異。

在 UP 主頁面按 **Fetch another range** 可以追加作品。已存在的影片會依 BV 號重複使用，重疊區間不需要重新抓取整個作品目錄。

**Capture snapshot** 會更新作品庫中的影片統計，形成新的時間快照。預設只更新最近 40 支影片，可在設定中調整為 30–50 支。這些快照會產生 UP 主頁的影片年齡增長曲線，以及影片詳情頁的播放歷史曲線。伺服器預設每 24 小時自動採集一次；可用 `STATS_REFRESH_HOURS` 調整，設為 `0` 則只保留手動採集。服務停機後重新啟動時，會立即補跑所有已逾期的 UP 主，而不是等下一輪檢查；停機期間缺少的時間點無法事後重建，因此第一個補跑快照會記在實際重啟時間。

同一背景更新也會保存 Bilibili 全站排行榜與最新一期「每週必看」。相符的上榜紀錄會出現在 UP 主彙總頁與影片詳情頁。

**抓取一定要 SESSDATA。** 每支影片都會經過的 `x/web-interface/view`，對沒有登入狀態的請求一律回 HTTP 412 —— 這是對線上 API 實測確認過的 —— 所以沒有 SESSDATA 的話，一開跑就直接失敗，不會只是功能少一半。要加上它：登入 bilibili.com，F12 → Application → Cookies → 複製 `SESSDATA`，貼到 Settings 裡。想先看看畫面，用上面的 demo seed。

## 安全性

這是一個**單人使用、沒有任何身分驗證的本機工具**。任何能連到這個 port 的人都能存取所有端點，所以 Compose 只把它綁定在 `127.0.0.1` 上。不要把這個 port 開放到你不能掌控的網路，也不要在沒有先加上身分驗證的情況下把它放到反向代理後面。

你的 SESSDATA 與 API key 在寫進 SQLite 之前，會先用 Fernet 加密，API 回傳時也會遮蔽顯示。加密金鑰放在 `DATA_DIR/.secret_key` —— 就在它所保護的資料庫旁邊，所以這只能防範單獨拿到 `.db` 檔案的情況，防不了對主機本身的存取。

## 技術棧

| Layer | |
|---|---|
| Frontend | Vite · React 19 · TypeScript · Tailwind CSS v4 · Base UI · ECharts |
| Backend | FastAPI · SQLAlchemy 2.0（async）· aiosqlite · httpx |
| 部署 | Docker Compose，單一 multi-stage image |

## 設定

| 變數 | 預設值 | |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/bilianalyzer.db` | 資料庫存放的位置 |
| `DATA_DIR` | `./data` | 存放資料庫與 `.secret_key` |
| `SECRET_KEY` | *(自動產生)* | Fernet 金鑰。第一次執行時產生並保存下來；如果想讓儲存的憑證能跨環境讀取，就明確設定這個值 |
| `CORS_ORIGINS` | `http://localhost:5173` | 只有前後端分離的開發模式才需要。留空就完全停用 CORS |
| `STATS_REFRESH_HOURS` | `24` | 背景統計快照的間隔小時數；`0` 表示停用自動快照 |

## 本機開發

```bash
# backend
cd backend && python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --port 8000 --reload

# frontend, in another terminal
cd frontend && npm install && npm run dev      # http://localhost:5173
```

在 `backend/` 底下跑 `pytest`，在 `frontend/` 底下跑 `npm test`、`npm run build` 和 `npx eslint .`。需要 Python 3.11+ 與 Node 20+。

## 授權

[MIT](LICENSE)
