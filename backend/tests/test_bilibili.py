# backend/tests/test_bilibili.py
import asyncio
from datetime import date

import httpx
import pytest

from app.services.bilibili import BilibiliBlockedError, BilibiliClient


def _offline_client() -> BilibiliClient:
    """A client with every network side-effect (fingerprint, proxy pool, wbi)
    already neutralised, so a test drives _request and nothing else."""
    client = BilibiliClient.__new__(BilibiliClient)
    client._sessdata = None
    client._img_key = None
    client._sub_key = None
    client._wbi_keys_ts = 0
    client._fingerprint_ready = True
    client._proxy_urls = []
    client._proxy_pool = None
    return client


def _silence_waits(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(BilibiliClient, "_throttle", _noop)
    monkeypatch.setattr("app.services.bilibili.asyncio.sleep", _noop)


def test_get_mixin_key():
    """Test mixin key derivation from img_key + sub_key using known values."""
    client = BilibiliClient.__new__(BilibiliClient)
    # Use known test vectors from bilibili-API-collect
    img_key = "7cd084941338484aae1ad9425b84077c"
    sub_key = "4932caff0ff746eab6f01bf08b70ac45"
    mixin_key = client._get_mixin_key(img_key + sub_key)
    assert len(mixin_key) == 32
    assert isinstance(mixin_key, str)


def test_sign_params():
    client = BilibiliClient.__new__(BilibiliClient)
    client._img_key = "7cd084941338484aae1ad9425b84077c"
    client._sub_key = "4932caff0ff746eab6f01bf08b70ac45"
    params = {"mid": 546195}
    signed = client._sign_wbi(params)
    assert "w_rid" in signed
    assert "wts" in signed
    assert "mid" in signed


@pytest.mark.asyncio
async def test_validate_sessdata_returns_user_name():
    client = BilibiliClient.__new__(BilibiliClient)
    client._sessdata = "test-sessdata"

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False, use_proxy: bool = True):
        return {"code": 0, "data": {"isLogin": True, "uname": "Roxy"}}

    client._request = fake_request

    result = await client.validate_sessdata()

    assert result == {"uname": "Roxy"}


@pytest.mark.asyncio
async def test_validate_sessdata_raises_for_invalid_cookie():
    client = BilibiliClient.__new__(BilibiliClient)
    client._sessdata = "expired-sessdata"

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False, use_proxy: bool = True):
        return {"code": 0, "data": {"isLogin": False}}

    client._request = fake_request

    with pytest.raises(Exception, match="invalid or expired"):
        await client.validate_sessdata()


@pytest.mark.asyncio
async def test_aclose_ignores_missing_client():
    client = BilibiliClient.__new__(BilibiliClient)

    await client.aclose()


def test_normalize_video_stub_prefers_pubdate_and_strips_highlight():
    client = BilibiliClient.__new__(BilibiliClient)

    video = client._normalize_video_stub(
        {
            "bvid": "BV1test",
            "title": '<em class="keyword">Hello</em>',
            "pubdate": 200,
            "ctime": 100,
        },
        "rec_archives_full",
    )

    assert video == {
        "bvid": "BV1test",
        "title": "Hello",
        "published_ts": 200,
        "created": 200,
        "source": "rec_archives_full",
        "ctime": 100,
    }


def test_is_live_replay_video_matches_auto_uploaded_pattern_only():
    client = BilibiliClient.__new__(BilibiliClient)

    assert client._is_live_replay_video("【直播回放】超短电影回(已报备) 2026年03月29日20点场", []) is True
    assert client._is_live_replay_video("普通视频", ["【直播回放】舰礼等身抱枕套最后一天！嗷！ 2026年03月30日20点场"]) is True
    assert client._is_live_replay_video("【直播回放】我自己剪辑的总结视频", []) is False
    assert client._is_live_replay_video("普通视频", ["直播回放 2026-03-29"]) is False
    assert client._is_live_replay_video("普通视频", ["第一P", "第二P"]) is False


@pytest.mark.asyncio
async def test_get_video_index_in_range_uses_seed_only_when_seed_covers_requested_dates():
    client = BilibiliClient.__new__(BilibiliClient)
    calls = []

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        calls.append({"url": url, "params": params, "wbi": wbi})
        if params == {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0}:
            return {
                "code": 0,
                "data": {
                    "archives": [
                        {"bvid": "BV1", "title": "First", "pubdate": 1710028800},
                        {"bvid": "BV2", "title": "Second", "pubdate": 1709942400},
                        {"bvid": "BV3", "title": "【直播回放】超短电影回(已报备) 2024年03月08日20点场", "pubdate": 1709856000},
                    ],
                    "page": {"num": 0, "size": 20, "total": 999},
                },
            }
        raise AssertionError(f"unexpected params: {params}")

    client._request = fake_request

    result = await client.get_video_index_in_range(546195, date(2024, 3, 8), date(2024, 3, 10))

    assert calls == [{
        "url": "https://api.bilibili.com/x/series/recArchivesByKeywords",
        "params": {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0},
        "wbi": False,
    }]
    assert result["is_complete_snapshot"] is True
    assert [video["bvid"] for video in result["videos"]] == ["BV1", "BV2"]
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_get_video_index_in_range_uses_seed_and_paginated_fill_with_overlap_dedupe():
    client = BilibiliClient.__new__(BilibiliClient)
    calls = []

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        calls.append({"url": url, "params": params, "wbi": wbi})
        if params == {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0}:
            return {
                "code": 0,
                "data": {
                    "archives": [
                        {"bvid": "BV1", "title": '<em class="keyword">First</em>', "pubdate": 1710028800, "ctime": 1710028800},
                        {"bvid": "BV2", "title": "Second", "pubdate": 1709856000, "ctime": 1709856000},
                    ],
                    "page": {"num": 0, "size": 20, "total": 999},
                },
            }
        if params == {"mid": 546195, "keywords": "", "orderby": "senddate", "ps": 100, "pn": 1}:
            return {
                "code": 0,
                "data": {
                    "archives": [
                        {"bvid": "BV1", "title": "First", "pubdate": 1710028800, "ctime": 1710028800},
                        {"bvid": "BV2", "title": "Second", "pubdate": 1709856000, "ctime": 1709856000},
                        {"bvid": "BV3", "title": "Third", "pubdate": 1709251200, "ctime": 1709251200},
                    ],
                    "page": {"num": 1, "size": 3, "total": 6},
                },
            }
        raise AssertionError(f"unexpected params: {params}")

    client._request = fake_request

    result = await client.get_video_index_in_range(546195, date(2024, 3, 1), date(2024, 3, 10))

    assert calls == [
        {
            "url": "https://api.bilibili.com/x/series/recArchivesByKeywords",
            "params": {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0},
            "wbi": False,
        },
        {
            "url": "https://api.bilibili.com/x/series/recArchivesByKeywords",
            "params": {"mid": 546195, "keywords": "", "orderby": "senddate", "ps": 100, "pn": 1},
            "wbi": False,
        },
    ]
    assert result["is_complete_snapshot"] is True
    assert [video["bvid"] for video in result["videos"]] == ["BV1", "BV2", "BV3"]
    assert result["videos"][0]["title"] == "First"
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_get_video_index_in_range_stops_after_page_reaches_start_date():
    client = BilibiliClient.__new__(BilibiliClient)
    calls = []

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        calls.append(params)
        if params == {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0}:
            return {
                "code": 0,
                "data": {
                    "archives": [
                        {"bvid": "BV1", "title": "First", "pubdate": 1710201600},
                        {"bvid": "BV2", "title": "Second", "pubdate": 1710115200},
                    ],
                    "page": {"num": 0, "size": 20, "total": 999},
                },
            }
        if params == {"mid": 546195, "keywords": "", "orderby": "senddate", "ps": 100, "pn": 1}:
            return {
                "code": 0,
                "data": {
                    "archives": [
                        {"bvid": "BV3", "title": "Third", "pubdate": 1709942400},
                        {"bvid": "BV4", "title": "Fourth", "pubdate": 1709164800},
                    ],
                    "page": {"num": 1, "size": 2, "total": 999},
                },
            }
        raise AssertionError(f"unexpected params: {params}")

    client._request = fake_request

    result = await client.get_video_index_in_range(546195, date(2024, 2, 29), date(2024, 3, 12))

    assert calls == [
        {"mid": 546195, "keywords": "", "orderby": "senddate", "pn": 0},
        {"mid": 546195, "keywords": "", "orderby": "senddate", "ps": 100, "pn": 1},
    ]
    assert [video["bvid"] for video in result["videos"]] == ["BV1", "BV2", "BV3", "BV4"]
    assert result["is_complete_snapshot"] is True


@pytest.mark.asyncio
async def test_get_video_index_in_range_falls_back_to_arc_search():
    client = BilibiliClient.__new__(BilibiliClient)
    calls = []

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        calls.append({"url": url, "params": params, "wbi": wbi})
        if url.endswith("/x/series/recArchivesByKeywords"):
            return {"code": -504, "message": "服务调用超时"}
        if url.endswith("/x/space/wbi/arc/search"):
            if params["pn"] == 1:
                return {
                    "code": 0,
                    "data": {
                        "list": {
                            "vlist": [
                                {"bvid": "BV1", "title": "First", "created": 1710201600},
                                {"bvid": "BV2", "title": "Second", "created": 1710115200},
                                *[
                                    {
                                        "bvid": f"BVFILLER{index}",
                                        "title": "Outside range",
                                        "created": 1710374400,
                                    }
                                    for index in range(48)
                                ],
                            ]
                        },
                        "page": {"count": 51},
                    },
                }
            if params["pn"] == 2:
                return {
                    "code": 0,
                    "data": {
                        "list": {
                            "vlist": [
                                {"bvid": "BV3", "title": "Third", "created": 1710028800},
                            ]
                        },
                        "page": {"count": 51},
                    },
                }
        raise AssertionError(f"unexpected request: {url} {params}")

    client._request = fake_request

    result = await client.get_video_index_in_range(
        546195, date(2024, 3, 10), date(2024, 3, 12)
    )

    assert [call["url"] for call in calls] == [
        "https://api.bilibili.com/x/series/recArchivesByKeywords",
        "https://api.bilibili.com/x/space/wbi/arc/search",
        "https://api.bilibili.com/x/space/wbi/arc/search",
    ]
    assert calls[1]["wbi"] is True
    assert calls[2]["wbi"] is True
    assert result["source"] == "arc_search"
    assert [video["bvid"] for video in result["videos"]] == ["BV1", "BV2", "BV3"]
    assert result["is_complete_snapshot"] is True


@pytest.mark.asyncio
async def test_request_retries_transient_412_for_non_wbi_calls():
    client = BilibiliClient.__new__(BilibiliClient)
    client._fingerprint_ready = True
    client._proxy_urls = []  # no proxy pool — the shared throttle state needs no setup
    sleep_calls = []
    calls = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    async def fake_throttle(via_proxy: bool = False):
        return None

    class FakeClient:
        async def get(self, url: str, params=None):
            calls.append({"url": url, "params": params})
            request = httpx.Request("GET", url, params=params)
            if len(calls) < 3:
                return httpx.Response(412, request=request)
            return httpx.Response(200, request=request, json={"code": 0, "data": {"ok": True}})

    client._ensure_fingerprint = fake_throttle
    client._throttle = fake_throttle
    client._client = FakeClient()

    original_sleep = asyncio.sleep
    asyncio.sleep = fake_sleep
    try:
        result = await client._request("https://example.com/test", params={"a": 1})
    finally:
        asyncio.sleep = original_sleep

    assert result == {"code": 0, "data": {"ok": True}}
    assert len(calls) == 3
    assert len(sleep_calls) == 2


def test_filter_live_replay_stubs_removes_auto_uploaded_replays():
    client = BilibiliClient.__new__(BilibiliClient)

    videos = client._filter_live_replay_stubs([
        {"bvid": "BV1", "title": "【直播回放】超短电影回(已报备) 2026年03月29日20点场"},
        {"bvid": "BV2", "title": "普通投稿"},
    ])

    assert videos == [{"bvid": "BV2", "title": "普通投稿"}]


@pytest.mark.asyncio
async def test_request_retries_transient_412_for_wbi_calls_and_refreshes_keys():
    client = BilibiliClient.__new__(BilibiliClient)
    client._fingerprint_ready = True
    client._proxy_urls = []  # no proxy pool — the shared throttle state needs no setup
    client._img_key = "img"
    client._sub_key = "sub"
    client._wbi_keys_ts = 0
    sleep_calls = []
    refresh_calls = []
    signed_params = []
    calls = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    async def fake_noop(via_proxy: bool = False):
        return None

    async def fake_refresh():
        refresh_calls.append(True)
        client._img_key = "img"
        client._sub_key = "sub"
        client._wbi_keys_ts = 9999999999

    def fake_sign(params: dict) -> dict:
        signed = {**params, "w_rid": "rid", "wts": 1}
        signed_params.append(signed)
        return signed

    class FakeClient:
        async def get(self, url: str, params=None):
            calls.append({"url": url, "params": params})
            request = httpx.Request("GET", url, params=params)
            if len(calls) < 3:
                return httpx.Response(412, request=request)
            return httpx.Response(200, request=request, json={"code": 0, "data": {"ok": True}})

    client._ensure_fingerprint = fake_noop
    client._throttle = fake_noop
    client._refresh_wbi_keys = fake_refresh
    client._sign_wbi = fake_sign
    client._client = FakeClient()

    original_sleep = asyncio.sleep
    asyncio.sleep = fake_sleep
    try:
        result = await client._request("https://example.com/wbi", params={"mid": 1}, wbi=True)
    finally:
        asyncio.sleep = original_sleep

    assert result == {"code": 0, "data": {"ok": True}}
    assert len(calls) == 3
    assert len(refresh_calls) >= 1
    assert len(signed_params) == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_get_video_index_keeps_complete_snapshot_true_after_live_replay_filtering():
    client = BilibiliClient.__new__(BilibiliClient)

    async def fake_total(uid: int):
        assert uid == 546195
        return 3

    async def fake_full(uid: int):
        assert uid == 546195
        return {
            "videos": [
                {"bvid": "BV2", "title": "Second", "published_ts": 100, "created": 100, "source": "rec_archives_full"},
                {"bvid": "BV1", "title": "First", "published_ts": 200, "created": 200, "source": "rec_archives_full"},
                {"bvid": "BV3", "title": "【直播回放】超短电影回(已报备) 2026年03月29日20点场", "published_ts": 300, "created": 300, "source": "rec_archives_full"},
            ],
            "total": 3,
            "is_complete_snapshot": True,
        }

    client._get_expected_video_total = fake_total
    client._video_index_via_rec_archives_full = fake_full

    result = await client.get_video_index(546195)

    assert result == {
        "videos": [
            {"bvid": "BV1", "title": "First", "published_ts": 200, "created": 200, "source": "rec_archives_full"},
            {"bvid": "BV2", "title": "Second", "published_ts": 100, "created": 100, "source": "rec_archives_full"},
        ],
        "total": 2,
        "expected_total": 3,
        "source": "rec_archives_full",
        "is_complete_snapshot": True,
    }


@pytest.mark.asyncio
async def test_get_video_index_marks_incomplete_when_fetched_videos_do_not_reach_expected_total():
    client = BilibiliClient.__new__(BilibiliClient)

    async def fake_total(uid: int):
        assert uid == 546195
        return 5

    async def fake_full(uid: int):
        assert uid == 546195
        return {
            "videos": [
                {"bvid": "BV2", "title": "Second", "published_ts": 100, "created": 100, "source": "rec_archives_full"},
                {"bvid": "BV1", "title": "First", "published_ts": 200, "created": 200, "source": "rec_archives_full"},
                {"bvid": "BV3", "title": "【直播回放】超短电影回(已报备) 2026年03月29日20点场", "published_ts": 300, "created": 300, "source": "rec_archives_full"},
            ],
            "total": 5,
            "is_complete_snapshot": False,
        }

    client._get_expected_video_total = fake_total
    client._video_index_via_rec_archives_full = fake_full

    result = await client.get_video_index(546195)

    assert result["total"] == 2
    assert result["expected_total"] == 5
    assert result["is_complete_snapshot"] is False


@pytest.mark.asyncio
async def test_get_video_detail_marks_live_replay():
    client = BilibiliClient.__new__(BilibiliClient)
    client.BASE = BilibiliClient.BASE

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        if url.endswith("/x/web-interface/view"):
            return {
                "code": 0,
                "data": {
                    "bvid": "BV1",
                    "aid": 1,
                    "cid": 2,
                    "title": "【直播回放】超短电影回(已报备) 2026年03月29日20点场",
                    "owner": {"mid": 946974},
                    "desc": "",
                    "pic": "http://example.com/cover.jpg",
                    "duration": 100,
                    "pubdate": 123,
                    "stat": {
                        "view": 1,
                        "like": 2,
                        "coin": 3,
                        "favorite": 4,
                        "share": 5,
                        "danmaku": 6,
                        "reply": 7,
                    },
                    "pages": [
                        {"page": 1, "cid": 2, "part": "【直播回放】超短电影回(已报备) 2026年03月29日20点场"}
                    ],
                },
            }
        if url.endswith("/x/tag/archive/tags"):
            return {"code": 0, "data": []}
        raise AssertionError(f"unexpected url: {url}")

    client._request = fake_request

    result = await client.get_video_detail("BV1")

    assert result["is_live_replay"] is True
    assert result["owner_uid"] == 946974


@pytest.mark.asyncio
async def test_get_user_info_includes_creator_totals():
    client = BilibiliClient.__new__(BilibiliClient)
    client.BASE = BilibiliClient.BASE

    async def fake_request(url: str, params: dict | None = None, wbi: bool = False):
        if url.endswith("/x/web-interface/card"):
            return {
                "code": 0,
                "data": {
                    "card": {
                        "name": "Creator",
                        "face": "avatar.jpg",
                        "fans": 100,
                        "attention": 7,
                    },
                    "follower": 101,
                    "archive_count": 55,
                    "like_num": 900,
                },
            }
        if url.endswith("/x/relation/stat"):
            return {"code": 0, "data": {"follower": 102, "following": 8}}
        if url.endswith("/x/space/upstat"):
            return {
                "code": 0,
                "data": {"archive": {"view": 10000}, "likes": 1000},
            }
        if url.endswith("/x/space/navnum"):
            return {"code": 0, "data": {"video": 56}}
        raise AssertionError(f"unexpected url: {url}")

    client._request = fake_request
    result = await client.get_user_info(42)

    assert result["name"] == "Creator"
    assert result["followers"] == 102
    assert result["following"] == 8
    assert result["creator_total_views"] == 10000
    assert result["creator_total_likes"] == 1000
    assert result["archive_count"] == 56


@pytest.mark.asyncio
async def test_get_video_list_slices_video_index_result():
    client = BilibiliClient.__new__(BilibiliClient)

    async def fake_index(uid: int):
        assert uid == 546195
        return {
            "videos": [
                {"bvid": "BV1", "published_ts": 300, "created": 300},
                {"bvid": "BV2", "published_ts": 200, "created": 200},
                {"bvid": "BV3", "published_ts": 100, "created": 100},
            ]
        }

    client.get_video_index = fake_index

    result = await client.get_video_list(546195, page=2, page_size=2)

    assert result == {
        "videos": [{"bvid": "BV3", "published_ts": 100, "created": 100}],
        "total": 3,
        "page": 2,
    }


@pytest.mark.asyncio
async def test_persistent_412_raises_blocked_error(monkeypatch):
    """412 is Bilibili's risk control, not a transient failure.

    Once the retries are spent it has to surface as BilibiliBlockedError naming
    SESSDATA, because a bare HTTPStatusError only ever said "Precondition
    Failed" and the whole query died with nothing the user could act on.
    """
    client = _offline_client()
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(412)

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    _silence_waits(monkeypatch)

    with pytest.raises(BilibiliBlockedError) as exc:
        await client._request(f"{BilibiliClient.BASE}/x/web-interface/view", {"bvid": "BV1"})

    assert "SESSDATA" in str(exc.value)
    assert len(calls) == 3, "should give up after the retry budget, not keep hammering"
    await client._client.aclose()


@pytest.mark.asyncio
async def test_412_that_recovers_still_retries(monkeypatch):
    """The retry itself must survive: a 412 that clears on the next attempt is
    a real case (wbi keys going stale), and turning 412 into a hard failure
    everywhere would have broken it."""
    client = _offline_client()
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(412)
        return httpx.Response(200, json={"code": 0, "data": {"title": "ok"}})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    _silence_waits(monkeypatch)

    data = await client._request(f"{BilibiliClient.BASE}/x/web-interface/view", {"bvid": "BV1"})

    assert data["code"] == 0
    assert data["data"]["title"] == "ok"
    assert len(calls) == 2
    await client._client.aclose()
