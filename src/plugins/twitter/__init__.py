import json
from pathlib import Path
import random

from bs4 import BeautifulSoup
import httpx
import nonebot
from nonebot import get_plugin_config, get_bot
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import MessageSegment

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

memepic = on_command("meme")


@memepic.handle()
async def handle_function():
    tmpf = TwitterMemePicForwarder()
    images = tmpf.get_random_pic()
    if not images:
        await memepic.finish("没有找到meme qwq")
    msg = MessageSegment.image(images[0])
    await memepic.finish(msg)


@scheduler.scheduled_job("cron", hour="*/2", id="meme_job")
async def scheduled_meme():
    tmpf = TwitterMemePicForwarder()
    images = tmpf.get_random_pic()
    if not images:
        return

    try:
        bot = get_bot()
    except ValueError:
        return
    for group_id in config.group_ids:
        for img_url in images:
            msg = MessageSegment.image(img_url)
            await bot.send_group_msg(group_id=group_id, message=msg)


class TwitterMemePicForwarder:
    def __init__(self):
        self.username = config.twitter_id
        self.url = config.api_url
        self.proxy = config.proxy

    def get_user_twitter(self) -> list:
        response = httpx.get(
            self.url,
            headers={"User-Agent": "edge"},
            timeout=30,
            proxy=config.proxy,
            follow_redirects=True,
        )
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
            tweet = entry.get("content", {})
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
