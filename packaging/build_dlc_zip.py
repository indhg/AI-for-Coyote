# -*- coding: utf-8 -*-
"""DLC 整包构建脚本：把内置内容整理成「一整个 zip」随 DLC 仓库分发。

用法：
    python packaging/build_dlc_zip.py 1.1.6

输出：
    build_release/Coyote-in-Cradle-DLC-v<版本>.zip

zip 结构与主发布包完全一致（顶层 content/）：
    content/pure            体验版（触手·纯爱试玩）
    content/roles           正式角色稿（触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后）
    content/pack/dungeon    地牢主题包（地牢刻印 + 触手 / 品评会 / 哥布林 / 淫纹）

规则：与 packaging/build_release.py 保持同源——EN 稿（*-EN.md）与 .git 不随包；
pack 目录的 .github / LICENSE / README 等随包保留（与主包一致）。
"""
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

VERSION = next((a for a in sys.argv[1:] if not a.startswith("--")), "0.0.0")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build_release"
PKG = BUILD / f"Coyote-in-Cradle-DLC-v{VERSION}"
ZIP = BUILD / f"Coyote-in-Cradle-DLC-v{VERSION}.zip"


def copy_content(src: Path, dst: Path) -> None:
    """带忽略规则的目录拷贝（规则与主包 build_release.py 一致）。"""
    if not src.exists():
        raise SystemExit(f"缺少 {src}：请确认内容目录存在")
    ignore = shutil.ignore_patterns("*-EN.md", ".git", "__pycache__")
    shutil.copytree(src, dst, ignore=ignore)


def main() -> None:
    print(f"=== DLC 整包 v{VERSION} ===", flush=True)
    if PKG.exists():
        shutil.rmtree(PKG)
    (PKG / "content").mkdir(parents=True)

    step = "1/3 角色内容（pure + roles）"
    print(f"=== {step} ===", flush=True)
    for name in ("pure", "roles"):
        copy_content(ROOT / "content" / name, PKG / "content" / name)

    step = "2/3 地牢主题包"
    print(f"=== {step} ===", flush=True)
    pack = ROOT / "content" / "pack"
    if pack.exists():
        shutil.copytree(
            pack, PKG / "content" / "pack",
            ignore=shutil.ignore_patterns("*-EN.md", ".git", "__pycache__"),
        )
    else:
        print("[警告] 缺少 content/pack，跳过地牢主题包", flush=True)

    step = "3/3 压缩"
    print(f"=== {step} ===", flush=True)
    if ZIP.exists():
        ZIP.unlink()
    shutil.make_archive(str(ZIP.with_suffix("")), "zip", PKG.parent, PKG.name)
    print(f"完成：{ZIP}（{ZIP.stat().st_size / 1024 / 1024:.1f} MB）", flush=True)


if __name__ == "__main__":
    main()
