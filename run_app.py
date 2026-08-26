# -*- coding: utf-8 -*-
"""运行/打包统一入口。

- 开发运行：python run_app.py
- 发布打包：pyinstaller run_app.py（见 packaging/build_release.py）
打包后以 exe 所在目录为项目根（config/、content/、frontend/dist 与 exe 同级）。
"""
import sys
from pathlib import Path

# 打包后把 exe 所在目录（配置文件所在）加入搜索路径，保证 backend 包可导入
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).resolve().parent))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from backend.config import load_config  # noqa: E402


def main() -> None:
    cfg = load_config()
    from backend.main import app  # noqa: E402

    uvicorn.run(
        app,
        host=cfg["app"]["host"],
        port=int(cfg["app"]["port"]),
        log_level="info",
    )


if __name__ == "__main__":
    main()
