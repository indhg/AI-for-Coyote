# -*- coding: utf-8 -*-
"""更新检测：启动 + 每 6 小时静默查 GitHub Releases 最新版本，失败静默不打扰。"""
import logging
import re
import time

import httpx

logger = logging.getLogger("ai-for-coyote.update")

RELEASE_API = "https://api.github.com/repos/indhg/AI-for-Coyote/releases/latest"
CHECK_INTERVAL_S = 6 * 3600
USER_AGENT = "CoyoteInCradle-UpdateCheck"


def parse_version(s: str) -> tuple[int, int, int] | None:
    """从任意版本串里取 x.y.z 数字段（忽略 dev/desk 后缀与 v 前缀）。"""
    m = re.match(r"[vV]?(\d+)\.(\d+)\.(\d+)", str(s or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class UpdateChecker:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self.latest: str = ""  # 最新 tag，如 v1.1.4
        self.url: str = ""     # Release 页面地址
        self.last_checked = 0.0

    async def check(self) -> None:
        if not self.enabled:
            return
        now = time.time()
        if self.latest and now - self.last_checked < CHECK_INTERVAL_S:
            return
        self.last_checked = now
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                r = await client.get(RELEASE_API, headers={"User-Agent": USER_AGENT})
                if r.status_code != 200:
                    return
                data = r.json()
                tag = str(data.get("tag_name") or "").strip()
                if not tag.startswith("v"):
                    return
                self.latest = tag
                self.url = str(data.get("html_url") or "")
                logger.info("更新检查：最新版本 %s", tag)
        except Exception as exc:  # noqa: BLE001
            logger.debug("更新检查失败（静默）: %s", exc)

    def available(self, current: str) -> bool:
        cur = parse_version(current)
        latest = parse_version(self.latest)
        return bool(cur and latest and latest > cur)

    def to_state(self, current: str) -> dict:
        return {
            "enabled": self.enabled,
            "latest": self.latest,
            "url": self.url,
            "available": self.available(current),
        }
