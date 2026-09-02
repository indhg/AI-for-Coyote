# -*- coding: utf-8 -*-
"""更新检测：启动 + 每 6 小时静默查「更新源」最新版本，失败静默不打扰。

更新源可配置（config.yaml → app.update_url）：
  - 留空 + check_update=true ：查 GitHub Releases（旧行为，向后兼容）
  - 填自定义 URL             ：查自建源（推荐），支持 JSON：
      { "version": "v1.1.6", "download_url": "https://...", "notes": "更新说明" }
      （也兼容 GitHub release JSON 的 tag_name / html_url 字段）
  - check_update=false       ：完全关闭，不联网
"""
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
    def __init__(self, enabled: bool = True, url: str = "") -> None:
        self.enabled = bool(enabled)
        # 源：显式 update_url 优先；为空且开启时回退 GitHub（向后兼容）
        self.api_url = (url or "").strip() or RELEASE_API
        if not self.enabled:
            self.api_url = ""  # 关闭时完全不联网
        self.latest: str = ""  # 最新版本号，如 v1.1.6
        self.url: str = ""     # 下载/跳转地址
        self.notes: str = ""   # 更新说明（自定义源可选）
        self.last_checked = 0.0

    async def check(self) -> None:
        if not self.enabled or not self.api_url:
            return
        now = time.time()
        if self.latest and now - self.last_checked < CHECK_INTERVAL_S:
            return
        self.last_checked = now
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                r = await client.get(self.api_url, headers={"User-Agent": USER_AGENT})
                if r.status_code != 200:
                    return
                data = r.json()
                # 自定义源：version/download_url/notes；GitHub 源：tag_name/html_url
                tag = str(data.get("version") or data.get("tag_name") or "").strip()
                if not parse_version(tag):
                    return
                self.latest = tag
                self.url = str(data.get("download_url") or data.get("html_url") or "").strip()
                self.notes = str(data.get("notes") or "").strip()
                logger.info("更新检查：最新版本 %s（源 %s）", tag, self.api_url)
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
            "notes": self.notes,
            "available": self.available(current),
        }
