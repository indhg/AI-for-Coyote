# -*- coding: utf-8 -*-
"""DLC 整包构建脚本：内置内容按语言拆成两个大包，随 DLC 仓库分发。

用法：
    python packaging/build_dlc_zip.py 1.1.6 zh
    python packaging/build_dlc_zip.py 1.1.6 en

输出：
    build_release/Coyote-in-Cradle-DLC-zh-v<版本>.zip   中文大包
    build_release/Coyote-in-Cradle-DLC-en-v<版本>.zip   英文大包

内容（与主发布包同源、同规则）：
    content/pure            体验版（触手·纯爱试玩）
    content/roles           正式角色稿（触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后）
    content/pack/dungeon    地牢主题包（地牢刻印 + 触手 / 品评会 / 哥布林 / 淫纹）

- zh 包：中文内容（不含 -EN.md，规则与 packaging/build_release.py 一致）
- en 包：仅英文稿（*-EN.md，保持 content/ 相对结构与文件名，程序按 -EN 同目录匹配加载）
  地牢主题包当前无英文稿，故 en 包只含 pure + roles 的英文部分。
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
    """中文大包：pure + roles + pack 全量（排除 -EN.md / .git）。"""
    step("1/2 角色内容（pure + roles）")
    for name in ("pure", "roles"):
        src = ROOT / "content" / name
        if not src.exists():
            print(f"[警告] 缺少 content/{name}，跳过", flush=True)
            continue
        shutil.copytree(src, PKG / "content" / name,
                        ignore=shutil.ignore_patterns("*-EN.md", ".git", "__pycache__"))
    step("2/2 地牢主题包")
    pack = ROOT / "content" / "pack"
    if pack.exists():
        shutil.copytree(pack, PKG / "content" / "pack",
                        ignore=shutil.ignore_patterns("*-EN.md", ".git", "__pycache__"))
    else:
        print("[警告] 缺少 content/pack，跳过地牢主题包", flush=True)


def copy_en() -> None:
    """英文大包：全内容树中收集 *-EN.md，保持 content/ 相对结构。"""
    step("1/1 收集英文稿（*-EN.md）")
    root_content = ROOT / "content"
    if not root_content.exists():
        raise SystemExit("缺少 content/")
    n = 0
    for f in sorted(root_content.rglob("*-EN.md")):
        rel = f.relative_to(root_content)          # 如 roles/触手-角色提示词-EN.md
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
