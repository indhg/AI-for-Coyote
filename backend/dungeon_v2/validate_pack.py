# -*- coding: utf-8 -*-
"""校验器 CLI：python -m backend.dungeon_v2.validate_pack <pack_dir> [--no-wave-check]

退出码：0 = 通过（可有 warning/note）；1 = 有 error（包会被拒绝加载）；2 = 目录/文件读不出来。
"""
from __future__ import annotations

import sys
from pathlib import Path

from .cli import utf8_console
from .errors import DungeonError
from .loader import known_patterns_default, load_tree
from .schema import validate_tree


def main(argv: list[str] | None = None) -> int:
    utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    wave_check = "--no-wave-check" not in argv
    path = Path([a for a in argv if not a.startswith("--")][0])
    try:
        tree = load_tree(path)
    except DungeonError as exc:
        print(f"READ-ERROR {exc.zh}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"READ-ERROR {exc}")
        return 2
    res = validate_tree(tree, known_patterns_default() if wave_check else None)
    print(f"包：{path}  事件数：{len(tree.get('events') or {})}")
    print(res.report())
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
