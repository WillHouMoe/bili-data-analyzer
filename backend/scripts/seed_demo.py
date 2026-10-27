"""Seed the local database with fictional video metadata and performance data.

This gives a fresh clone a populated dashboard without requiring Bilibili
credentials or a live scrape. All rows belong to an obviously fictional creator.

Usage (from the backend/ directory, with dependencies installed):

    python scripts/seed_demo.py            # seed once; no-op if already seeded
    python scripts/seed_demo.py --reset    # delete existing demo data and reseed
"""
import argparse
import asyncio
import random
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import async_session, init_db  # noqa: E402
from app.models import Query, QueryVideo, User, Video, VideoStats  # noqa: E402

RNG_SEED = 20260831
DEMO_UID = 9999900001
DEMO_USER_NAME = "陈万能的实验室（演示账号）"
DEMO_AVATAR = "https://i0.hdslb.com/bfs/face/member/noface.jpg"

TAG_POOL = [
    "DIY", "手工", "极客", "生活黑客", "测评", "改造", "开箱", "维修",
    "教程", "沙雕", "翻车现场", "废物利用", "电子", "冷知识", "居家",
]

TITLES = [
    "用微波炉的零件做了一台空气炸锅",
    "花三天把十年前的老风扇改造成静音款",
    "拆解一台祖传录音机,里面全是惊喜",
    "把废旧键盘做成了一个机械键盘台灯",
    "自制水冷散热器,压不住我也认了",
    "花两百块挑战复刻一台咖啡机",
    "把旧手机改造成监控摄像头教程",
    "用3D打印机修好了朋友的破椅子",
    "拆开十年前买的假货充电宝,后果自负",
    "自己动手做了一个能语音控制的台灯",
    "把废弃自行车轮做成了一台发电机",
    "花一下午修好了漏水二十年的老水龙头",
    "用纸箱做了一台能用的投影仪",
    "改造老式收音机,塞进了蓝牙模块",
    "自制小型风力发电装置全过程记录",
    "把坏掉的显示器拆了看看里面长什么样",
    "用乐高零件拼了一个能动的机械臂",
    "花一整天给旧笔记本换了固态硬盘",
    "自制简易3D打印机,成本不到五百",
    "把废旧空调外机改造成小冰箱",
    "拆解网红榨汁机,测测到底值不值",
    "用面包板搭了一个会眨眼的电子猫",
    "改造老年手机,加装了紧急呼叫按钮",
    "自己动手接了一整套智能家居开关",
    "把旧吉他音箱改成了蓝牙音响",
    "花一周时间给猫做了一个自动喂食器",
    "拆开十年前的诺基亚,居然还能开机",
    "自制简易电动滑板车测试全过程",
    "把废旧显卡改造成了一个暖手宝",
    "用锡纸和电池做了一个应急手电筒",
    "改造老式缝纫机,变成了自动版本",
    "花一下午修好了朋友的机械键盘",
    "自制小型温室,冬天也能种菜",
    "拆解共享单车锁,看看到底多难破解",
    "用旧路由器搭了一个迷你NAS",
    "把废旧木板做成了一整面工具墙",
    "自制简易空气净化器,效果测试",
    "改造老旧台灯,加了无线充电底座",
    "花两天时间给房间做了隐藏布线",
    "拆开十年前的老式电视,内部很震撼",
    "自制简易机械键盘轴体测试台",
    "把废弃洗衣机电机改造成了小风扇",
    "用手机零件拼了一个能用的对讲机",
    "改造老式自行车,加装了电助力",
    "自制迷你气象站,在家也能测天气",
    "花一整天给旧电脑主机做静音改造",
    "拆解网红加湿器,内部结构大公开",
    "用废旧齿轮做了一个机械时钟",
    "把旧显示器改造成了触控一体机",
    "自制简易过滤水壶,效果实测",
    "改造老式风扇,加装了定时和遥控",
]


def _gen_duration(rng: random.Random) -> int:
    bucket = rng.choices(["short", "standard", "long"], weights=[2, 5, 3])[0]
    if bucket == "short":
        return rng.randint(45, 180)
    if bucket == "standard":
        return rng.randint(300, 900)
    return rng.randint(1000, 3600)


def _gen_views(rng: random.Random) -> int:
    tier = rng.choices(["normal", "hit", "viral"], weights=[7, 2, 1])[0]
    if tier == "normal":
        return rng.randint(2_000, 60_000)
    if tier == "hit":
        return rng.randint(60_000, 300_000)
    return rng.randint(300_000, 1_500_000)


def _weighted_hour(rng: random.Random) -> int:
    weights = [1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 8, 9, 7, 6, 6, 7, 8, 10, 12, 11, 9, 6, 3]
    return rng.choices(range(24), weights=weights, k=1)[0]


def _gen_publish_dates(
    rng: random.Random, count: int, start: date, end: date
) -> list[datetime]:
    offsets = sorted(rng.sample(range((end - start).days + 1), k=count))
    return [
        datetime(
            (start + timedelta(days=offset)).year,
            (start + timedelta(days=offset)).month,
            (start + timedelta(days=offset)).day,
            _weighted_hour(rng),
            rng.randint(0, 59),
            tzinfo=UTC,
        )
        for offset in offsets
    ]


async def _reset_demo_data(db) -> None:
    queries = (
        await db.execute(select(Query).where(Query.uid == DEMO_UID))
    ).scalars().all()
    for query in queries:
        await db.delete(query)
    await db.flush()

    videos = (
        await db.execute(select(Video).where(Video.bvid.like("BVDEMO%")))
    ).scalars().all()
    for video in videos:
        await db.delete(video)
    await db.flush()

    user = await db.get(User, DEMO_UID)
    if user:
        await db.delete(user)
    await db.commit()


async def seed(reset: bool) -> None:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    await init_db()
    async with async_session() as db:
        existing_user = await db.get(User, DEMO_UID)
        existing_query = (
            await db.execute(select(Query).where(Query.uid == DEMO_UID))
        ).scalars().first()

        if existing_user and existing_query and not reset:
            print(
                f"Demo data already present (query_id={existing_query.id}, "
                f"{existing_query.video_count} videos). Use --reset to regenerate."
            )
            return

        if existing_user or existing_query:
            print("Resetting existing (or partial) demo data...")
            await _reset_demo_data(db)

        rng = random.Random(RNG_SEED)
        db.add(
            User(
                uid=DEMO_UID,
                name=DEMO_USER_NAME,
                avatar_url=DEMO_AVATAR,
                last_fetched_at=datetime.now(UTC),
            )
        )

        video_count = rng.randint(38, 52)
        start_date = date(2025, 11, 15)
        end_date = date(2026, 8, 25)
        publish_dates = _gen_publish_dates(rng, video_count, start_date, end_date)

        titles = rng.sample(TITLES, k=min(video_count, len(TITLES)))
        while len(titles) < video_count:
            titles.append(rng.choice(TITLES))
        rng.shuffle(titles)

        query = Query(
            uid=DEMO_UID,
            user_name=DEMO_USER_NAME,
            start_date=start_date,
            end_date=end_date,
            status="done",
            progress=None,
            video_count=video_count,
        )
        db.add(query)
        await db.flush()

        totals = {
            "views": 0,
            "likes": 0,
            "coins": 0,
            "favorites": 0,
            "shares": 0,
            "danmaku": 0,
            "comments": 0,
        }

        for index, (published_at, title) in enumerate(
            zip(publish_dates, titles), start=1
        ):
            bvid = f"BVDEMO{index:04d}"
            duration = _gen_duration(rng)
            tags = ",".join(rng.sample(TAG_POOL, k=rng.randint(2, 4)))
            views = _gen_views(rng)
            likes = int(views * rng.uniform(0.03, 0.12))
            coins = int(likes * rng.uniform(0.2, 0.6))
            favorites = int(likes * rng.uniform(0.15, 0.5))
            shares = int(likes * rng.uniform(0.02, 0.15))
            comment_count = rng.randint(20, 400)
            danmaku_count = rng.randint(10, 600)

            db.add(
                Video(
                    bvid=bvid,
                    uid=DEMO_UID,
                    title=title,
                    description=f"{title} —— 演示数据,仅用于本地效果展示,非真实投稿。",
                    cover_url="https://i0.hdslb.com/bfs/archive/demo-cover.jpg",
                    duration=duration,
                    published_at=published_at,
                    tags=tags,
                )
            )
            db.add(
                VideoStats(
                    bvid=bvid,
                    views=views,
                    likes=likes,
                    coins=coins,
                    favorites=favorites,
                    shares=shares,
                    danmaku_count=danmaku_count,
                    comment_count=comment_count,
                )
            )
            db.add(QueryVideo(query_id=query.id, bvid=bvid))

            totals["views"] += views
            totals["likes"] += likes
            totals["coins"] += coins
            totals["favorites"] += favorites
            totals["shares"] += shares
            totals["danmaku"] += danmaku_count
            totals["comments"] += comment_count

        query.total_views = totals["views"]
        query.total_likes = totals["likes"]
        query.total_coins = totals["coins"]
        query.total_favorites = totals["favorites"]
        query.total_shares = totals["shares"]
        query.total_danmaku = totals["danmaku"]
        query.total_comments = totals["comments"]

        await db.commit()
        print(
            f"Seeded demo query id={query.id} with {video_count} videos "
            f"for uid={DEMO_UID} ({DEMO_USER_NAME})."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo data before reseeding",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()
