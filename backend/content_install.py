# -*- coding: utf-8 -*-
"""内容/语言包安装（程序内入口的后端）：接收 zh/en 大包 zip，合并进 content/。

zip 兼容两种顶层形态（均由 packaging/build_dlc_zip.py 产出）：
    content/…（如 content/roles/触手-角色提示词.md、content/roles/…-EN.md）
    或直接 pure/…、roles/…、pack/…

安全规则：
- 仅允许文本/数据/图片类扩展名（*.md *.yaml *.yml *.txt *.json *.png *.jpg
  *.jpeg *.gif *.webp），可执行文件一律拒绝；
- 跳过 .git / .github / __pycache__ / 点文件；
- 路径规范化后必须落在 content/ 内（防 ../ 穿越）；
- 总量与条目数设上限，防 zip 炸弹。
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

# 错误消息按当前 UI 语言返回，这里同时携带中文与英文
class ContentInstallError(Exception):
    def __init__(self, zh: str, en: str | None = None) -> None:
        super().__init__(zh)
        self.zh = zh
        self.en = en or zh


_ALLOWED_EXT = {
    ".md", ".yaml", ".yml", ".txt", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
}
_SKIP_PARTS = {".git", ".github", "__pycache__", ".gitignore"}
_MAX_ZIP_BYTES = 256 * 1024 * 1024      # 上传体积上限 256MB
_MAX_TOTAL_BYTES = 1024 * 1024 * 1024   # 解压总量上限 1GB（zip 炸弹保护）
_MAX_FILES = 20_000


def install_zip_bytes(data: bytes, content_root: Path) -> dict:
    """把 zip 内容合并进 content_root，返回 {ok, files, sections, added, updated}。"""
    if not data:
        raise ContentInstallError("zip 为空", "the zip is empty")
    if len(data) > _MAX_ZIP_BYTES:
        raise ContentInstallError("zip 超过 256MB 上限", "zip exceeds the 256MB limit")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ContentInstallError("不是有效的 zip 文件", "not a valid zip file") from None

    root = content_root.resolve()
    todo: list[tuple[str, Path, int]] = []   # (entry_name, target, size)
    sections: set[str] = set()
    total = 0
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            total += info.file_size
            if total > _MAX_TOTAL_BYTES:
                raise ContentInstallError("zip 解压后过大（超过 1GB）", "unzipped content is too large")
            raw = info.filename.replace("\\", "/")
            if raw.startswith("/") or raw.startswith("~") or any(p == ".." for p in raw.split("/")):
                raise ContentInstallError("zip 含有不安全路径，已拒绝安装", "the zip contains an unsafe path")
            parts = [p for p in raw.split("/") if p]
            if not parts:
                continue
            # 兼容发布包外层目录/content/...，以及直接 content/... 或 pure/...。
            if parts[0] == "content":
                parts = parts[1:]
            elif len(parts) > 1 and parts[1] == "content":
                parts = parts[2:]
            if not parts:
                continue
            if parts[0].startswith(".") or any(p in _SKIP_PARTS for p in parts):
                continue
            ext = Path(parts[-1]).suffix.lower()
            if ext not in _ALLOWED_EXT:
                continue  # 非内容文件（含可执行文件）静默忽略
            target = (root / Path(*parts)).resolve()
            if not target.is_relative_to(root):
                continue  # 防穿越
            sections.add(parts[0])
            todo.append((info.filename, target, info.file_size))
        if not todo:
            raise ContentInstallError(
                "zip 里没有可安装的内容（需含 content/pure、content/roles 或 content/pack 下的 md/yaml/图片）",
                "the zip contains no installable content "
                "(expected content/pure, content/roles or content/pack .md/.yaml/images)",
            )
        if len(todo) > _MAX_FILES:
            raise ContentInstallError("zip 内文件过多", "too many files in the zip")

        added = updated = 0
        for entry, target, _ in todo:
            existed = target.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry) as src:
                target.write_bytes(src.read())
            if existed:
                updated += 1
            else:
                added += 1

    return {
        "ok": True,
        "files": len(todo),
        "added": added,
        "updated": updated,
        "sections": sorted(sections),
    }
