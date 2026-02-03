from pydantic import BaseModel
from typing import Optional, List


class Config(BaseModel):
    """Plugin Config Here"""

    twitter_id: Optional[str] = "elonmusk"
    group_ids: List[int] = []  # 要发送的QQ群号列表

    @property
    def api_url(self) -> str:
        return f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{self.twitter_id}"

    proxy: Optional[str] = "http://127.0.0.1:10808"
