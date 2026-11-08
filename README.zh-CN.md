# BiliDataAnalyzer

一个用来解读 Bilibili 创作者视频表现的仪表板：某段时间内发布了什么、表现如何，以及这些数字如何累积。

<p>
  <a href="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml"><img src="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/WillHouMoe/bili-data-analyzer" alt="License: MIT"></a>
</p>

[English](README.md) · **简体中文**

Bilibili 的创作中心只给你看自己账号的总数和几条趋势线。BiliDataAnalyzer 能跨越一位创作者近期的作品回答更广泛的问题：哪些视频表现最好、发布节奏和视频时长与关注度有什么关系，以及互动如何随时间累积。它接受任何公开的 UID，所以无论是创作者回顾自己的作品、粉丝或分析者研究别人，还是比较两位创作者，都用得上。

给它一个 UID 和一段日期范围，它就会抓取创作者在那段时间内发布的每一个视频，并将表现数据绘制成图表。

评论、弹幕和字幕正文刻意不在范围内。应用会保留 Bilibili 视频统计数据提供的评论和弹幕“数量”，但不会抓取或存储底层正文。

![仪表板](docs/images/dashboard.png)

## 快速开始

需要 Docker 和 Docker Compose。

```bash
git clone https://github.com/WillHouMoe/bili-data-analyzer.git
cd bili-data-analyzer
./bilia start
```

这会在后台启动应用，并在首次运行时根据示例创建 `.env`。之后用 `./bilia open` 打开；需要时可用 `./bilia status` 和 `./bilia logs`。API 文档位于与 UI 相同端口的 `/docs`。

在 macOS 上运行一次 `./bilia install-login`，登录系统时就会自动启动 Docker 和分析服务；之后每五分钟还会检查一次，并在需要时重启容器。可用 `./bilia uninstall-login` 移除。启动输出位于 `/tmp/bilianalyzer-background.log`。`./bilia stop` 和 `./bilia down` 会在当前登录会话中卸载启动代理，避免手动停止后五分钟又被启动。

抓取在服务器进程中执行。提交抓取后可以直接关闭浏览器；之后打开仪表板只会读取已保存的结果，不会重新抓取。如果容器在抓取过程中重启，未完成的批次会继续运行，并跳过已写入的视频。

### 立刻查看有数据的界面

抓取真实创作者的数据需要一段时间，而且必须有 `SESSDATA` cookie。如果想在没有 cookie 的情况下让每个面板都显示像样的数据，可以：

```bash
docker compose exec app python -m scripts.seed_demo
```

这会生成一个虚构创作者，并附带几个月的视频元数据和表现数据。加上 `--reset` 可以重新开始。

## 使用方法

1. **Add creator** —— 输入创作者的 UID（即 `space.bilibili.com/546195` 中的数字），并选择日期范围。侧边栏会显示抓取进度。
2. **Dashboard** —— 摘要卡片、观看数趋势、互动数比较、观看数与互动率散点图、时长分析和发布节奏。目录现在以 UP 主为单位，单次抓取只是其下的批次；账号总粉丝、总播放和总获赞来自 Bilibili 的 UP 主统计接口。视频快照按每个作品的发布年龄安排，粉丝、账号播放和账号获赞历史另存为 UP 主快照，并以两张并排图表展示：左侧是粉丝，右侧是账号播放和获赞。作品库跨度超过一年时，发布日历可按年份切换，并在日历右侧显示对应年份的年度摘要。
3. **Video detail** —— 单个视频的数据，与该视频发布前 180 天内最近 20 条作品组成同期基准。雷达图显示各项指标的同期分位，增减栏与同期中位数比较，避免全历史平均值被账号增长期拉低。

在 UP 主页面点击 **Fetch another range** 可以追加视频。已有视频会按 BV 号复用，因此重叠日期范围不需要重新抓取整个作品目录。UP 主加入作品库后，后台还会检查其最新投稿，并自动为尚未入库的新视频建立记录。

**Refresh due data** 会更新 UP 主账号总数和已经到期的视频快照。维护按视频发布年龄安排，而不是按视频数量截断：发布后第 1 天内每小时一次，1–3 天每 2 小时一次，3–7 天每 4 小时一次，7–14 天每 8 小时一次，14–30 天每 12 小时一次，30–365 天每天一次。默认的一年窗口会在一年后停止自动维护；不限时间模式会继续每周采集。若播放量突然加速或视频新上榜，下一次采集会提前一档，并最多维持 6 次观察。

这些快照会生成 UP 主页面的视频年龄增长曲线，以及视频详情页的播放历史曲线。UP 主账号总数默认每 24 小时采集一次；可用 `STATS_REFRESH_HOURS` 调整，设为 `0` 则只保留手动刷新。服务停机后重新启动时，后台会按到期顺序跨所有 UP 主补跑，而不是等待新的 24 小时周期；停机期间缺失的时间点无法事后补建，因此第一个补跑快照会记录在实际重启时间。

后台成就回填会读取每个作品库视频保留的 `honor_reply`，取得其全部“每周必看”期数和全站排行榜历史最高名次。两类长期成就与当前榜单分组展示在 UP 主汇总页和视频详情页。

**抓取必须提供 SESSDATA。** 每个视频都会经过的 `x/web-interface/view`，对没有登录状态的请求一律返回 HTTP 412——这一点已通过线上 API 实测确认——所以没有 SESSDATA 时会直接失败，而不是只缺少部分功能。添加方法：登录 bilibili.com，按 F12 → Application → Cookies，复制 `SESSDATA`，粘贴到 Settings 中。想先看看界面，可以使用上面的演示数据。

## 安全性

这是一个**单人使用、没有任何身份验证的本地工具**。任何能连接到该端口的人都能访问所有端点，因此 Compose 只将它绑定到 `127.0.0.1`。不要将该端口开放到你无法控制的网络，也不要在未先添加身份验证的情况下把它放在反向代理后面。

你的 SESSDATA 和 API 密钥在写入 SQLite 之前，会先用 Fernet 加密，API 返回时也会以掩码显示。加密密钥存放在 `DATA_DIR/.secret_key`——就在它所保护的数据库旁边，因此这只能防范有人单独获取 `.db` 文件，无法防范对主机的访问。

## 用 GitHub Pages 发布只读网站

公网网站是静态数据快照，本地实例始终是唯一的数据写入端：抓取、刷新快照和保存凭据都只在本地完成。导出器复用 API 的响应模型，只发布仪表板与视频页需要的 UP 主、视频和统计数据；`app_settings`、AI 会话、凭据和 SQLite 数据库都不会进入静态构建。

本地收集好要公开的数据后运行：

```bash
./bilia publish-static
```

这会生成 `frontend/public/static-data/snapshot.json`，只提交该快照并使用 `data: refresh public dashboard snapshot` 作为提交信息，然后推送当前的 `main` 或 `simplify` 分支。导出失败时不会执行 Git 操作；快照没有变化时会跳过空提交。[静态 Pages 工作流](.github/workflows/pages.yml) 会检查快照、以只读模式构建前端，并部署 `frontend/dist`。

如果只想在本地重新生成快照、不提交也不推送，请运行 `./bilia export-static`。

在 GitHub 仓库的 **Settings → Pages** 中首次选择 **GitHub Actions** 作为来源。项目站点会发布到 `https://<owner>.github.io/<repository>/`，工作流会根据仓库名自动设置子路径。

静态版本会隐藏新增 UP 主、刷新统计、删除和 Settings 入口。搜索、排序和分页都在浏览器中基于导出的视频库完成。公网数据只会在提交并部署新快照后更新；它不会抓取 Bilibili，也不会写入数据。

本地预览静态版本：

```bash
cd frontend
VITE_STATIC_MODE=true VITE_BASE_PATH=/ npm run build
npm run preview
```

如果为 GitHub Pages 绑定自定义域名，请将 `.github/workflows/pages.yml` 中的 `VITE_BASE_PATH` 改为 `/`。GitHub Pages 的内容是公开的，只应导出你准备公开的数据。

## 技术栈

| 层级 | |
|---|---|
| 前端 | Vite · React 19 · TypeScript · Tailwind CSS v4 · Base UI · ECharts |
| 后端 | FastAPI · SQLAlchemy 2.0（异步）· aiosqlite · httpx |
| 本地部署 | Docker Compose，单一多阶段镜像 |
| 公网只读 | GitHub Pages，脱敏 JSON 快照 |

## 配置

| 变量 | 默认值 | |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/bilianalyzer.db` | 数据库存放位置 |
| `DATA_DIR` | `./data` | 存放数据库与 `.secret_key` |
| `SECRET_KEY` | *（自动生成）* | Fernet 密钥。首次运行时生成并持久保存；如需让已保存的凭据能跨环境读取，就显式设置该值 |
| `CORS_ORIGINS` | `http://localhost:5173` | 仅前后端分离的开发环境需要。留空会完全停用 CORS |
| `STATS_REFRESH_HOURS` | `24` | UP 主账号快照间隔（小时）；视频按上面的发布年龄区间采集；`0` 表示停用自动快照 |
| `RANKING_REFRESH_MINUTES` | `15` | 独立的全站排行榜轮询间隔；名次变化会立即将对应视频加入成就刷新队列；`0` 表示停用榜单轮询 |
| `NEW_VIDEO_REFRESH_MINUTES` | `30` | 扫描已跟踪 UP 主的最新投稿并补建未入库视频；`0` 表示停用自动发现 |

## 本地开发

```bash
# backend
cd backend && python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --port 8000 --reload

# frontend, in another terminal
cd frontend && npm install && npm run dev      # http://localhost:5173
```

在 `backend/` 中运行 `pytest`，在 `frontend/` 中运行 `npm test`、`npm run build` 和 `npx eslint .`。需要 Python 3.11+ 和 Node 20+。

## 许可

[MIT](LICENSE)
