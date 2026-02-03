import asyncio
import base64
import json
from pathlib import Path
import random
from datetime import datetime

from bs4 import BeautifulSoup
import httpx
import nonebot
from nonebot import get_plugin_config, get_bot
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import MessageSegment, Bot, GroupMessageEvent

from .config import Config
from nonebot import on_command
from nonebot import require

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

__plugin_meta__ = PluginMetadata(
    name="twitter meme pic forwarder",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

# 图片缓存
_image_cache: list[str] = []
_cache_last_refresh: datetime | None = None
CACHE_REFRESH_INTERVAL = 3600  # 缓存刷新间隔（秒）

memepic = on_command("meme")


def download_image_as_base64(url: str) -> str | None:
    """下载图片并转换为 base64"""
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": "edge"},
            timeout=30,
            proxy=config.proxy,
            follow_redirects=True,
        )
        if response.status_code == 200:
            return "base64://" + base64.b64encode(response.content).decode()
    except Exception:
        pass
    return None


def refresh_cache():
    """刷新图片缓存"""
    global _image_cache, _cache_last_refresh
    tmpf = TwitterMemePicForwarder()
    tweets = tmpf.get_user_twitter()
    _image_cache = []
    for tweet in tweets:
        _image_cache.extend(tweet["images"])
    _cache_last_refresh = datetime.now()
    print(f"缓存已刷新，共 {len(_image_cache)} 张图片")


def get_cached_image() -> str | None:
    """从缓存获取随机图片，必要时刷新缓存"""
    global _image_cache, _cache_last_refresh

    # 检查是否需要刷新缓存
    need_refresh = (
        not _image_cache or
        _cache_last_refresh is None or
        (datetime.now() - _cache_last_refresh).total_seconds() > CACHE_REFRESH_INTERVAL
    )

    if need_refresh:
        refresh_cache()

    if not _image_cache:
        return None

    return random.choice(_image_cache)


@memepic.handle()
async def handle_function(bot: Bot, event: GroupMessageEvent):
    try:
        await bot.call_api("set_msg_emoji_like", message_id=event.message_id, emoji_id="181")
    except Exception:
        pass
    await asyncio.sleep(0.5)
    img_url = get_cached_image()
    if not img_url:
        await memepic.finish("没有找到meme qwq")
    img_base64 = download_image_as_base64(img_url)
    if not img_base64:
        await memepic.finish("图片下载失败 qwq")
    msg = MessageSegment.image(img_base64)
    await memepic.send(msg)
    await memepic.finish()


@scheduler.scheduled_job("cron", hour="*/2", id="meme_job")
async def scheduled_meme():
    img_url = get_cached_image()
    if not img_url:
        return

    img_base64 = download_image_as_base64(img_url)
    if not img_base64:
        return

    try:
        bot = get_bot()
    except ValueError:
        return

    for group_id in config.group_ids:
        msg = MessageSegment.image(img_base64)
        await bot.send_group_msg(group_id=group_id, message=msg)


# 定时刷新缓存（每小时）
@scheduler.scheduled_job("cron", minute="0", id="cache_refresh_job")
async def scheduled_cache_refresh():
    refresh_cache()


class TwitterMemePicForwarder:
    def __init__(self):
        self.username = config.twitter_id
        self.url = config.api_url
        self.proxy = config.proxy

    def get_user_twitter(self) -> list:
        try:
            response = httpx.get(
                self.url,
                headers={"User-Agent": "edge"},
                timeout=30,
                proxy=config.proxy,
                follow_redirects=True,
            )
        except httpx.ConnectError as e:
            print(f"代理连接失败: {config.proxy}, 错误: {e}")
            return []
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            return []

        data = json.loads(script.string)
        entries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("timeline", {})
            .get("entries", [])
        )
        tweets = []
        for entry in entries:
            if entry.get("type") != "tweet":
                continue
            tweet = entry.get("content", {}).get("tweet", {})
            if not tweet:
                continue

            media = tweet.get("entities", {}).get("media", [])
            images = [
                m.get("media_url_https") for m in media if m.get("type") == "photo"
            ]
            if images:
                tweets.append(
                    {
                        "id": tweet.get("conversation_id_str"),
                        "text": tweet.get("full_text", "")[:100],
                        "user": tweet.get("user", {}).get("screen_name"),
                        "images": images,
                        "likes": tweet.get("favorite_count", 0),
                    }
                )

        return tweets

    def get_random_pic(self):
        tweets = self.get_user_twitter()
        if not tweets:
            return []
        tweet = random.choice(tweets)
        return tweet["images"]
