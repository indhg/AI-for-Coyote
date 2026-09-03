# -*- coding: utf-8 -*-
"""DLC 整包构建脚本：内置内容按语言拆成两个大包，随 DLC 仓库分发。

用法：
    python packaging/build_dlc_zip.py 1.1.6 zh
    python packaging/build_dlc_zip.py 1.1.6 en

输出：
    build_release/Coyote-in-Cradle-DLC-zh-v<版本>.zip   中文大包
    build_release/Coyote-in-Cradle-DLC-en-v<版本>.zip   英文大包

内容（2026-09-03 用户定版）：
    content/pure            纯爱体验版（触手·纯爱）——内置在主发布包，不走 DLC
    content/roles           5 个正式角色稿（触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后）——DLC 主体
    content/pack/dungeon    地牢主题包——已随「地牢重做」废弃归档，不进入任何发行包

- zh 包：仅 content/roles（5 个正式角色中文稿）
- en 包：仅英文稿（*-EN.md，含 pure EN + roles EN，保持 content/ 相对结构与文件名，
  程序按 -EN 同目录匹配加载；主包内置 pure CN，切 EN 需本包提供 pure EN）
- 地牢主题包一律不打入 DLC（旧包废弃，新地牢未成型）
"""
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
VERSION = args[0] if args else "0.0.0"
LANG = (args[1] if len(args) > 1 else "zh").lower()
if LANG not in ("zh", "en"):
    raise SystemExit("LANG 只能是 zh 或 en")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build_release"
PKG = BUILD / f"Coyote-in-Cradle-DLC-{LANG}-v{VERSION}"
ZIP = BUILD / f"Coyote-in-Cradle-DLC-{LANG}-v{VERSION}.zip"


def copy_zh() -> None:
    """中文大包：仅 content/roles（5 个正式角色稿）。

    pure（纯爱体验版）内置在主发布包不走 DLC；地牢主题包已随地牢重做废弃归档。
    """
    step("1/1 正式角色稿（content/roles）")
    src = ROOT / "content" / "roles"
    if not src.exists():
        raise SystemExit("缺少 content/roles，无法构建 zh 包")
    shutil.copytree(src, PKG / "content" / "roles",
                    ignore=shutil.ignore_patterns("*-EN.md", ".git", "__pycache__"))


def copy_en() -> None:
    """英文大包：pure + roles 内收集 *-EN.md，保持 content/ 相对结构（地牢不打入）。"""
    step("1/1 收集英文稿（*-EN.md）")
    n = 0
    for name in ("pure", "roles"):
        src = ROOT / "content" / name
        if not src.exists():
            continue
        for f in sorted(src.rglob("*-EN.md")):
            rel = f.relative_to(ROOT / "content")     # 如 roles/触手-角色提示词-EN.md
            dst = PKG / "content" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            n += 1
            print(f"  + content/{rel}", flush=True)
    if n == 0:
        print("[警告] 未找到任何 *-EN.md 英文稿", flush=True)


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def main() -> None:
    print(f"=== DLC {LANG.upper()} 大包 v{VERSION} ===", flush=True)
    if PKG.exists():
        shutil.rmtree(PKG)
    (PKG / "content").mkdir(parents=True)
    (copy_zh if LANG == "zh" else copy_en)()
    step("压缩")
    if ZIP.exists():
        ZIP.unlink()
    shutil.make_archive(str(ZIP.with_suffix("")), "zip", PKG.parent, PKG.name)
    print(f"完成：{ZIP}（{ZIP.stat().st_size / 1024 / 1024:.2f} MB）", flush=True)


if __name__ == "__main__":
    main()
