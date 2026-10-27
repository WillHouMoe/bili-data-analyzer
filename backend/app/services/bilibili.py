# backend/app/services/bilibili.py
import asyncio
import hashlib
import logging
import random
import re
import time
import urllib.parse
import uuid
from datetime import UTC, datetime

import httpx

from app.core.time import as_china_time
from app.services.proxy_pool import ProxyPool, redact_url

logger = logging.getLogger(__name__)


class BilibiliBlockedError(RuntimeError):
    """Bilibili refused the request outright with HTTP 412.

    This is risk control, not a transient failure. The endpoints this app relies
    on (x/web-interface/view in particular) answer 412 to any request without a
    logged-in session, so retrying or rotating proxies never turns it into a 200
    when SESSDATA is missing or expired.
    """


# Shared across every BilibiliClient instance so that concurrent scrapes (e.g.
# two /api/fetch requests) cannot together double the effective request rate
# into Bilibili's -799 risk control. A per-instance semaphore/delay would let
# each client believe it alone is being polite.
_THROTTLE_STATE = {
    "semaphore": asyncio.Semaphore(1),
    "last_request_time": 0.0,
    "rate_limit_count": 0,
    "base_delay": 1.5,
}
# Standard WBI mixin key permutation table
MIXIN_KEY_ENC_TAB = [
    46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,
    33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,
    61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,
    36,20,34,44,52
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Sec-Ch-Ua-Platform": '"Windows"',
}


class BilibiliClient:
    BASE = "https://api.bilibili.com"
    _WBI_KEY_TTL = 600  # refresh WBI keys every 10 minutes

    def __init__(self, sessdata: str | None = None, proxy_urls: list[str] | None = None):
        self._sessdata = sessdata
        self._img_key: str | None = None
        self._sub_key: str | None = None
        self._wbi_keys_ts: float = 0
        self._fingerprint_ready = False
        self._proxy_urls = proxy_urls or []
        self._proxy_pool: ProxyPool | None = None
        cookies = {
            "buvid3": f"{uuid.uuid4()}infoc",
            "b_nut": str(int(time.time())),
        }
        if sessdata:
            cookies["SESSDATA"] = sessdata
        self._client = httpx.AsyncClient(
            headers=HEADERS, cookies=cookies, timeout=30,
        )

    async def aclose(self):
        client = getattr(self, "_client", None)
        if client is not None:
            await client.aclose()
        proxy_pool = getattr(self, "_proxy_pool", None)
        if proxy_pool:
            await proxy_pool.aclose()

    async def _ensure_proxy_pool(self) -> ProxyPool | None:
        if not self._proxy_urls:
            return None
        if self._proxy_pool is None:
            self._proxy_pool = ProxyPool(self._proxy_urls)
            await self._proxy_pool.initialize()
        return self._proxy_pool

    def _get_mixin_key(self, orig: str) -> str:
        return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]

    async def _ensure_fingerprint(self):
        """Upgrade buvid cookies with API-provided values (best-effort)."""
        if self._fingerprint_ready:
            return
        self._fingerprint_ready = True
        try:
            resp = await self._client.get(f"{self.BASE}/x/frontend/finger/spi")
            data = resp.json().get("data", {})
            b3 = data.get("b_3", "")
            b4 = data.get("b_4", "")
            if b3:
                self._client.cookies["buvid3"] = b3
            if b4:
                self._client.cookies["buvid4"] = b4
            logger.debug("Fingerprint cookies set: buvid3=%s, buvid4=%s", b3[:8], b4[:8] if b4 else "")
        except Exception as e:
            logger.debug("Failed to fetch fingerprint from API (using local): %s", e)

    @staticmethod
    def _sanitize(value: str) -> str:
        """Remove characters that break WBI signature verification."""
        for ch in "!'()*":
            value = value.replace(ch, "")
        return value

    def _sign_wbi(self, params: dict) -> dict:
        mixin_key = self._get_mixin_key(self._img_key + self._sub_key)
        params = {
            **params,
            "dm_img_list": "[]",
            "dm_img_str": "V2ViR0wgMS4w",
            "dm_cover_img_str": "QU5HTEUgKEludGVsLCBJbnRlbChSKSBVSEQgR3Jh",
            "wts": int(time.time()),
        }
        params = dict(sorted(params.items()))
        # Sanitize all values and convert to str before hashing
        sanitized = {k: self._sanitize(str(v)) for k, v in params.items()}
        query = urllib.parse.urlencode(sanitized)
        w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
        sanitized["w_rid"] = w_rid
        return sanitized

    async def _throttle(self, via_proxy: bool = False):
        """Ensure random delay between requests with dynamic adjustment.

        When via_proxy=True, use a much shorter delay since each proxy IP
        has its own rate-limit budget on Bilibili's side.
        """
        state = _THROTTLE_STATE
        async with state["semaphore"]:
            now = time.time()
            if via_proxy:
                delay = random.uniform(0.2, 0.6)
            else:
                delay = random.uniform(state["base_delay"], state["base_delay"] * 2.5)
            wait = max(0, delay - (now - state["last_request_time"]))
            if wait > 0:
                await asyncio.sleep(wait)
            state["last_request_time"] = time.time()

    async def _request(self, url: str, params: dict | None = None, wbi: bool = False, use_proxy: bool = True) -> dict:
        await self._ensure_fingerprint()
        raw_params = params or {}
        max_retries = 3
        data: dict | None = None

        # Determine which client to use
        pool = await self._ensure_proxy_pool() if use_proxy else None
        proxy_result = await pool.get_client() if pool else None
        active_client = proxy_result[0] if proxy_result else self._client
        active_entry = proxy_result[1] if proxy_result else None

        for attempt in range(max_retries):
            await self._throttle(via_proxy=active_entry is not None)
            request_params = raw_params
            if wbi:
                if not self._img_key or time.time() - self._wbi_keys_ts > self._WBI_KEY_TTL:
                    await self._refresh_wbi_keys()
                request_params = self._sign_wbi(raw_params)
            try:
                resp = await active_client.get(url, params=request_params)
            except (httpx.ConnectError, httpx.ProxyError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                if active_entry and pool:
                    pool.report_failure(active_entry)
                    logger.warning("Proxy %s connection error: %s, switching proxy", redact_url(active_entry.url), e)
                    proxy_result = await pool.get_client()
                    if proxy_result:
                        active_client, active_entry = proxy_result
                    else:
                        active_client, active_entry = self._client, None
                        logger.info("All proxies unavailable, falling back to direct connection")
                    continue
                raise
            if resp.status_code == 412:
                if active_entry and pool:
                    pool.report_failure(active_entry)
                    proxy_result = await pool.get_client()
                    if proxy_result:
                        active_client, active_entry = proxy_result
                    else:
                        active_client, active_entry = self._client, None
                if wbi:
                    await self._refresh_wbi_keys()
                if attempt < max_retries - 1:
                    delay = 1 + attempt * 2 + random.uniform(0, 0.5)
                    logger.warning(
                        "Received HTTP 412 from %s, retrying in %.1fs (attempt %d/%d)",
                        url, delay, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Retries are spent. Falling through to raise_for_status() here
                # produced a bare HTTPStatusError that said nothing about the
                # actual cause, which is almost always a missing or expired
                # SESSDATA rather than anything the caller can retry.
                raise BilibiliBlockedError(
                    "Bilibili rejected the request (HTTP 412). This endpoint requires a "
                    "logged-in session - set a valid SESSDATA in Settings and try again."
                )
            resp.raise_for_status()
            data = resp.json()
            code = data.get("code")
            # Retry on server timeout (-504) with proxy rotation
            if code == -504:
                if active_entry and pool:
                    pool.report_failure(active_entry)
                    proxy_result = await pool.get_client()
                    if proxy_result:
                        active_client, active_entry = proxy_result
                    else:
                        active_client, active_entry = self._client, None
                if attempt < max_retries - 1:
                    delay = 2 + attempt * 3 + random.uniform(0, 1)
                    logger.warning("Server timeout (-504) from %s, retrying in %.1fs (attempt %d/%d)", url, delay, attempt + 1, max_retries)
                    await asyncio.sleep(delay)
                    continue
            # Retry on rate limit (-799) with exponential backoff
            elif code == -799:
                _THROTTLE_STATE["rate_limit_count"] += 1
                if active_entry and pool:
                    pool.report_failure(active_entry)
                    proxy_result = await pool.get_client()
                    if proxy_result:
                        active_client, active_entry = proxy_result
                    else:
                        active_client, active_entry = self._client, None
                # Increase base delay (shared across all clients) if getting rate limited frequently
                if _THROTTLE_STATE["rate_limit_count"] >= 3:
                    _THROTTLE_STATE["base_delay"] = min(_THROTTLE_STATE["base_delay"] * 1.5, 5.0)
                    logger.warning("Frequent rate limits detected, increasing base delay to %.1fs", _THROTTLE_STATE["base_delay"])
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter: 3s, 9s, 27s
                    delay = (3 ** (attempt + 1)) + random.uniform(0, 2)
                    logger.warning("Rate limited (-799), retrying in %.1fs (attempt %d/%d)", delay, attempt + 1, max_retries)
                    await asyncio.sleep(delay)
                    continue
            else:
                # Reset rate limit counter on success
                if _THROTTLE_STATE["rate_limit_count"] > 0:
                    _THROTTLE_STATE["rate_limit_count"] = max(0, _THROTTLE_STATE["rate_limit_count"] - 1)
                if active_entry and pool:
                    pool.report_success(active_entry)
            return data
        if data is not None:
            return data
        raise Exception(f"Request to {url} exhausted retries without data")

    async def _refresh_wbi_keys(self):
        # Routed through _request so this is throttled/retried like every other
        # call — a direct self._client.get() here bypassed the shared rate limiter.
        resp = await self._request(f"{self.BASE}/x/web-interface/nav", use_proxy=False)
        data = resp["data"]
        img_url = data["wbi_img"]["img_url"]
        sub_url = data["wbi_img"]["sub_url"]
        self._img_key = img_url.rsplit("/", 1)[1].split(".")[0]
        self._sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
        self._wbi_keys_ts = time.time()

    # --- Public API methods ---

    async def validate_sessdata(self) -> dict:
        if not self._sessdata:
            raise Exception("SESSDATA not configured")
        data = await self._request(f"{self.BASE}/x/web-interface/nav", use_proxy=False)
        if data.get("code") != 0:
            raise Exception(f"Bilibili API error {data.get('code')}: {data.get('message')}")
        nav = data.get("data") or {}
        if not nav.get("isLogin"):
            raise Exception("SESSDATA is invalid or expired")
        uname = nav.get("uname") or ""
        return {"uname": uname}

    async def get_user_info(self, uid: int) -> dict:
        user_info: dict = {"uid": uid, "name": "", "avatar_url": ""}
        card_metrics: dict = {}
        # Primary: x/web-interface/card (less strict rate limiting)
        try:
            data = await self._request(
                f"{self.BASE}/x/web-interface/card",
                params={"mid": uid, "photo": "false"},
            )
            if data.get("code") == 0:
                payload = data["data"]
                card = payload["card"]
                user_info.update(
                    name=card["name"],
                    avatar_url=card["face"],
                )
                card_metrics = {
                    "followers": payload.get("follower") or card.get("fans"),
                    "following": card.get("attention"),
                    "archive_count": payload.get("archive_count"),
                    "creator_total_likes": payload.get("like_num"),
                }
            else:
                logger.info(
                    "card API returned code %s, falling back to acc/info",
                    data.get("code"),
                )
        except Exception as e:
            logger.info("card API failed (%s), falling back to acc/info", e)
        if not user_info["name"]:
            # Fallback: x/space/wbi/acc/info with WBI signing
            data = await self._request(
                f"{self.BASE}/x/space/wbi/acc/info",
                params={"mid": uid},
                wbi=True,
            )
            if data.get("code") != 0:
                raise Exception(f"Bilibili API error {data.get('code')}: {data.get('message')}")
            info = data["data"]
            user_info.update(name=info["name"], avatar_url=info["face"])

        metrics = await self.get_creator_metrics(uid)
        return {
            **user_info,
            **{key: value for key, value in card_metrics.items() if value is not None},
            **{key: value for key, value in metrics.items() if value is not None},
        }

    async def get_creator_metrics(self, uid: int) -> dict:
        metrics: dict = {}
        try:
            relation = await self._request(
                f"{self.BASE}/x/relation/stat",
                params={"vmid": uid},
            )
            if relation.get("code") == 0:
                data = relation.get("data") or {}
                metrics["followers"] = data.get("follower")
                metrics["following"] = data.get("following")
        except Exception as exc:
            logger.info("relation stats unavailable for uid %s: %s", uid, exc)

        try:
            upstat = await self._request(
                f"{self.BASE}/x/space/upstat",
                params={"mid": uid},
            )
            if upstat.get("code") == 0:
                data = upstat.get("data") or {}
                metrics["creator_total_views"] = (
                    data.get("archive") or {}
                ).get("view")
                metrics["creator_total_likes"] = data.get("likes")
        except Exception as exc:
            logger.info("UP stats unavailable for uid %s: %s", uid, exc)

        try:
            navnum = await self._request(
                f"{self.BASE}/x/space/navnum",
                params={"mid": uid},
            )
            if navnum.get("code") == 0:
                metrics["archive_count"] = (
                    navnum.get("data") or {}
                ).get("video")
        except Exception as exc:
            logger.info("archive count unavailable for uid %s: %s", uid, exc)
        return metrics

    def _normalize_ranking_item(
        self,
        item: dict,
        rank: int,
        kind: str,
        period: str,
        period_name: str | None,
    ) -> dict | None:
        bvid = item.get("bvid")
        owner = item.get("owner") or {}
        if not bvid or not owner.get("mid"):
            return None
        stats = item.get("stat") or {}
        return {
            "kind": kind,
            "period": period,
            "period_name": period_name,
            "rank": rank,
            "bvid": bvid,
            "title": item.get("title") or bvid,
            "owner_uid": int(owner["mid"]),
            "owner_name": owner.get("name") or "",
            "cover_url": item.get("pic"),
            "views": int(stats.get("view", 0) or 0),
            "likes": int(stats.get("like", 0) or 0),
            "score": float(item.get("score", 0) or 0),
        }

    async def get_site_ranking(self) -> list[dict]:
        data = await self._request(
            f"{self.BASE}/x/web-interface/ranking/v2",
            params={"rid": 0, "type": "all"},
        )
        if data.get("code") != 0:
            raise Exception(
                f"Bilibili API error {data.get('code')}: {data.get('message')}"
            )
        payload = data.get("data") or {}
        period = as_china_time(datetime.now(UTC)).date().isoformat()
        entries = []
        for index, item in enumerate(payload.get("list") or [], start=1):
            normalized = self._normalize_ranking_item(
                item,
                index,
                "popular",
                period,
                payload.get("note"),
            )
            if normalized:
                entries.append(normalized)
        return entries

    async def get_weekly_must_watch(self) -> list[dict]:
        series = await self._request(
            f"{self.BASE}/x/web-interface/popular/series/list"
        )
        if series.get("code") != 0:
            raise Exception(
                f"Bilibili API error {series.get('code')}: {series.get('message')}"
            )
        lists = (series.get("data") or {}).get("list") or []
        latest = next((item for item in lists if item.get("status") == 2), None)
        if latest is None:
            return []
        number = int(latest["number"])
        detail = await self._request(
            f"{self.BASE}/x/web-interface/popular/series/one",
            params={"number": number},
        )
        if detail.get("code") != 0:
            raise Exception(
                f"Bilibili API error {detail.get('code')}: {detail.get('message')}"
            )
        payload = detail.get("data") or {}
        period = f"weekly-{number}"
        entries = []
        for index, item in enumerate(payload.get("list") or [], start=1):
            normalized = self._normalize_ranking_item(
                item,
                index,
                "weekly",
                period,
                latest.get("name"),
            )
            if normalized:
                entries.append(normalized)
        return entries

    def _normalize_video_stub(self, raw: dict, source: str) -> dict | None:
        bvid = raw.get("bvid") or ""
        if not bvid:
            return None
        title = raw.get("title", "")
        if isinstance(title, str):
            title = title.replace('<em class="keyword">', "").replace("</em>", "")
        published_ts = raw.get("pubdate") or raw.get("created") or raw.get("ctime") or 0
        published_ts = int(published_ts) if published_ts else 0
        video = {
            "bvid": bvid,
            "title": title,
            "published_ts": published_ts,
            "created": published_ts,
            "source": source,
        }
        ctime = raw.get("ctime")
        if ctime is not None:
            video["ctime"] = int(ctime)
        return video

    def _dedupe_video_stubs(self, videos: list[dict]) -> list[dict]:
        deduped: dict[str, dict] = {}
        for video in videos:
            if not video or not video.get("bvid"):
                continue
            bvid = video["bvid"]
            current = deduped.get(bvid)
            if current is None:
                deduped[bvid] = dict(video)
                continue
            merged = dict(current)
            for key, value in video.items():
                if key in {"published_ts", "created", "ctime"}:
                    continue
                if not merged.get(key) and value not in (None, ""):
                    merged[key] = value
            best_ts = max(
                int(current.get("published_ts", 0) or 0),
                int(video.get("published_ts", 0) or 0),
            )
            if best_ts:
                merged["published_ts"] = best_ts
                merged["created"] = best_ts
            if "ctime" in current or "ctime" in video:
                merged["ctime"] = max(
                    int(current.get("ctime", 0) or 0),
                    int(video.get("ctime", 0) or 0),
                )
            deduped[bvid] = merged
        return sorted(
            deduped.values(),
            key=lambda item: int(item.get("published_ts", 0) or 0),
            reverse=True,
        )

    def _slice_video_page(self, videos: list[dict], page: int, page_size: int) -> dict:
        page = max(page, 1)
        page_size = max(page_size, 1)
        start = (page - 1) * page_size
        end = start + page_size
        return {"videos": videos[start:end], "total": len(videos), "page": page}

    @staticmethod
    def _video_stub_date(video: dict):
        published_ts = int(video.get("published_ts") or video.get("created") or 0)
        if published_ts <= 0:
            return None
        return datetime.fromtimestamp(published_ts, tz=UTC).date()

    def _filter_videos_by_date(self, videos: list[dict], start_date, end_date) -> list[dict]:
        results = []
        for video in videos:
            pub_date = self._video_stub_date(video)
            if pub_date is None:
                continue
            if start_date <= pub_date <= end_date:
                results.append(video)
        return results

    def _video_date_bounds(self, videos: list[dict]):
        dates = [pub_date for video in videos if (pub_date := self._video_stub_date(video)) is not None]
        if not dates:
            return None, None
        return max(dates), min(dates)

    async def _get_expected_video_total(self, uid: int) -> int | None:
        try:
            nav = await self._request(f"{self.BASE}/x/space/navnum", params={"mid": uid})
            return int(nav.get("data", {}).get("video", 0) or 0)
        except Exception as e:
            logger.info("navnum lookup failed for uid %s (%s)", uid, e)
            return None

    def _is_complete_video_index(self, result: dict, expected_total: int | None) -> bool:
        if result.get("is_complete_snapshot"):
            return True
        fetched_total = len(result.get("videos") or [])
        return bool(expected_total is not None and fetched_total >= expected_total)

    @staticmethod
    def _is_live_replay_text(text: str) -> bool:
        if not isinstance(text, str):
            return False
        return bool(re.match(r"^【直播回放】.+\d{4}年\d{2}月\d{2}日\d{2}点场$", text.strip()))

    def _is_live_replay_video(self, title: str, page_parts: list[str]) -> bool:
        if self._is_live_replay_text(title):
            return True
        return any(self._is_live_replay_text(part) for part in page_parts)

    def _filter_live_replay_stubs(self, videos: list[dict]) -> list[dict]:
        return [video for video in videos if not self._is_live_replay_text(video.get("title", ""))]

    async def get_video_index(self, uid: int) -> dict:
        expected_total = await self._get_expected_video_total(uid)
        try:
            result = await self._video_index_via_rec_archives_full(uid)
        except Exception as e:
            logger.warning(
                "recArchivesByKeywords unavailable for uid %s (%s); "
                "falling back to WBI arc/search",
                uid,
                e,
            )
            result = await self._video_index_via_arc_search(uid)
        raw_videos = self._dedupe_video_stubs(result.get("videos") or [])
        videos = self._filter_live_replay_stubs(raw_videos)
        is_complete = self._is_complete_video_index(result, expected_total)
        source = result.get("source") or "rec_archives_full"
        logger.info(
            "Video index fetched via %s for uid %s: expected=%s raw=%d unique=%d complete=%s",
            source, uid, expected_total, len(raw_videos), len(videos), is_complete,
        )
        return {
            "videos": videos,
            "total": len(videos),
            "expected_total": expected_total,
            "source": source,
            "is_complete_snapshot": is_complete,
        }

    async def get_video_index_in_range(self, uid: int, start_date, end_date) -> dict:
        try:
            result = await self._video_index_via_rec_archives_hybrid(uid, start_date, end_date)
        except Exception as e:
            logger.warning(
                "recArchivesByKeywords unavailable for uid %s (%s); "
                "falling back to WBI arc/search",
                uid,
                e,
            )
            result = await self._video_index_via_arc_search(uid, start_date=start_date)
        raw_videos = self._dedupe_video_stubs(result.get("videos") or [])
        ranged_videos = self._filter_videos_by_date(raw_videos, start_date, end_date)
        videos = self._filter_live_replay_stubs(ranged_videos)
        return {
            "videos": videos,
            "total": len(videos),
            "source": result.get("source") or "rec_archives_full",
            "is_complete_snapshot": bool(result.get("is_complete_snapshot")),
        }

    async def get_video_list(self, uid: int, page: int = 1, page_size: int = 50) -> dict:
        result = await self.get_video_index(uid)
        return self._slice_video_page(result["videos"], page, page_size)

    async def _fetch_rec_archives_page(self, uid: int, pn: int, ps: int | None = None) -> dict:
        params = {"mid": uid, "keywords": "", "orderby": "senddate", "pn": pn}
        if ps is not None:
            params["ps"] = ps
        data = await self._request(
            f"{self.BASE}/x/series/recArchivesByKeywords",
            params=params,
        )
        if data.get("code") != 0:
            raise Exception(f"Bilibili API error {data.get('code')}: {data.get('message')}")
        payload = data.get("data") or {}
        page_info = payload.get("page") or {}
        archives = payload.get("archives") or []
        videos = [
            video for item in archives
            if (video := self._normalize_video_stub(item, "rec_archives_full"))
        ]
        return {
            "videos": videos,
            "archives": archives,
            "page": page_info,
        }

    async def _fetch_arc_search_page(self, uid: int, pn: int, page_size: int = 50) -> dict:
        data = await self._request(
            f"{self.BASE}/x/space/wbi/arc/search",
            params={"mid": uid, "pn": pn, "ps": page_size, "order": "pubdate"},
            wbi=True,
        )
        if data.get("code") != 0:
            raise Exception(f"Bilibili API error {data.get('code')}: {data.get('message')}")
        payload = data.get("data") or {}
        raw_videos = payload.get("list", {}).get("vlist") or []
        videos = [
            video for item in raw_videos
            if (video := self._normalize_video_stub(item, "arc_search"))
        ]
        raw_page = payload.get("page") or {}
        return {
            "videos": videos,
            "raw_videos": raw_videos,
            "page": {
                "num": pn,
                "size": len(raw_videos),
                "total": int(raw_page.get("count", 0) or 0),
            },
        }

    async def _video_index_via_arc_search(self, uid: int, start_date=None) -> dict:
        """Fetch a creator's archive through the standard WBI-signed endpoint.

        This is the fallback for recArchivesByKeywords, which intermittently
        answers 412 or -504 even when SESSDATA is valid. When start_date is
        supplied, stop once the newest-to-oldest scan has passed that boundary.
        """
        page_size = 50
        max_pages = 200
        videos: list[dict] = []
        seen_page_signatures: set[tuple[str, ...]] = set()
        is_complete_snapshot = False
        result_total = 0

        for page_num in range(1, max_pages + 1):
            page_result = await self._fetch_arc_search_page(
                uid, pn=page_num, page_size=page_size
            )
            page_videos = page_result.get("videos") or []
            raw_videos = page_result.get("raw_videos") or []
            page_info = page_result.get("page") or {}
            result_total = max(result_total, int(page_info.get("total", 0) or 0))

            if not raw_videos:
                is_complete_snapshot = True
                break

            page_signature = tuple(video["bvid"] for video in page_videos if video.get("bvid"))
            if page_signature and page_signature in seen_page_signatures:
                logger.warning("Duplicate arc/search page detected for uid %s page %s", uid, page_num)
                break
            if page_signature:
                seen_page_signatures.add(page_signature)

            videos.extend(page_videos)
            videos = self._dedupe_video_stubs(videos)

            _, page_oldest = self._video_date_bounds(page_videos)
            if start_date is not None and page_oldest is not None and page_oldest <= start_date:
                is_complete_snapshot = True
                break
            if result_total and page_num * page_size >= result_total:
                is_complete_snapshot = True
                break
            if 0 < len(raw_videos) < page_size:
                is_complete_snapshot = True
                break

        return {
            "videos": videos,
            "total": result_total or len(videos),
            "source": "arc_search",
            "is_complete_snapshot": is_complete_snapshot,
        }

    async def _video_index_via_rec_archives_hybrid(self, uid: int, start_date, end_date) -> dict:
        page_size = 100
        max_pages = 100
        seed = await self._fetch_rec_archives_page(uid, pn=0)
        videos = list(seed.get("videos") or [])
        seed_newest, seed_oldest = self._video_date_bounds(videos)

        if seed_oldest is not None and seed_oldest <= start_date:
            return {
                "videos": self._dedupe_video_stubs(videos),
                "total": len(videos),
                "source": "rec_archives_full",
                "is_complete_snapshot": True,
            }

        seen_page_signatures: set[tuple[str, ...]] = set()
        is_complete_snapshot = False
        for page_num in range(1, max_pages + 1):
            page_result = await self._fetch_rec_archives_page(uid, pn=page_num, ps=page_size)
            page_videos = page_result.get("videos") or []
            archives = page_result.get("archives") or []
            page_info = page_result.get("page") or {}
            effective_page_size = int(page_info.get("size", page_size) or page_size)

            if not archives:
                is_complete_snapshot = True
                break

            page_signature = tuple(video["bvid"] for video in page_videos if video.get("bvid"))
            if page_signature and page_signature in seen_page_signatures:
                logger.warning("Duplicate recArchivesByKeywords page detected for uid %s page %s", uid, page_num)
                break
            if page_signature:
                seen_page_signatures.add(page_signature)

            page_newest, page_oldest = self._video_date_bounds(page_videos)
            if page_oldest is not None and page_oldest > end_date:
                continue

            videos.extend(page_videos)
            videos = self._dedupe_video_stubs(videos)

            if page_oldest is not None and page_oldest <= start_date:
                is_complete_snapshot = True
                break
            if 0 < len(archives) < effective_page_size:
                is_complete_snapshot = True
                break

        return {
            "videos": videos,
            "total": len(videos),
            "source": "rec_archives_full",
            "is_complete_snapshot": is_complete_snapshot,
        }

    async def _video_index_via_rec_archives_full(self, uid: int) -> dict:
        page_size = 100
        max_pages = 100
        videos: list[dict] = []
        seen_page_signatures: set[tuple[str, ...]] = set()
        is_complete_snapshot = False
        result_total = 0

        for page_num in range(1, max_pages + 1):
            page_result = await self._fetch_rec_archives_page(uid, pn=page_num, ps=page_size)
            page_videos = page_result.get("videos") or []
            archives = page_result.get("archives") or []
            page_info = page_result.get("page") or {}
            effective_page_size = int(page_info.get("size", page_size) or page_size)
            result_total = max(result_total, int(page_info.get("total", 0) or 0))

            if not archives:
                is_complete_snapshot = True
                break

            page_signature = tuple(video["bvid"] for video in page_videos if video.get("bvid"))
            if page_signature and page_signature in seen_page_signatures:
                logger.warning("Duplicate recArchivesByKeywords page detected for uid %s page %s", uid, page_num)
                break
            if page_signature:
                seen_page_signatures.add(page_signature)

            videos.extend(page_videos)
            deduped_videos = self._dedupe_video_stubs(videos)

            if 0 < len(archives) < effective_page_size:
                is_complete_snapshot = True
                videos = deduped_videos
                break
            if result_total and len(deduped_videos) >= result_total:
                is_complete_snapshot = True
                videos = deduped_videos
                break
            videos = deduped_videos

        return {
            "videos": videos,
            "total": result_total or len(videos),
            "source": "rec_archives_full",
            "is_complete_snapshot": is_complete_snapshot,
        }

    async def get_video_detail(self, bvid: str) -> dict:
        data = await self._request(
            f"{self.BASE}/x/web-interface/view",
            params={"bvid": bvid},
        )
        if data.get("code") != 0:
            raise Exception(f"Bilibili API error {data.get('code')}: {data.get('message')}")
        d = data["data"]
        stat = d["stat"]
        # /view doesn't include Tags separately; try to get from honor_reply or tag endpoint
        tags_str = ""
        try:
            tag_data = await self._request(
                f"{self.BASE}/x/tag/archive/tags",
                params={"bvid": bvid},
            )
            if tag_data.get("code") == 0:
                tags = tag_data.get("data") or []
                tags_str = ",".join(t["tag_name"] for t in tags if "tag_name" in t)
        except Exception:
            pass
        pages = d.get("pages") or []
        page_parts = [p.get("part", "") for p in pages]
        title = d["title"]
        return {
            "bvid": d["bvid"],
            "owner_uid": d.get("owner", {}).get("mid"),
            "is_live_replay": self._is_live_replay_video(title, page_parts),
            "title": title, "description": d.get("desc", ""),
            "cover_url": d["pic"], "duration": d["duration"],
            "published_at": d["pubdate"],
            "tags": tags_str,
            "stats": {
                "views": stat["view"], "likes": stat["like"],
                "coins": stat["coin"], "favorites": stat["favorite"],
                "shares": stat["share"], "danmaku_count": stat["danmaku"],
                "comment_count": stat["reply"],
            },
}
