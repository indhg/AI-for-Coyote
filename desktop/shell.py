# -*- coding: utf-8 -*-
"""Coyote in Cradle 桌面壳（方案 C）。

双击 exe：静默拉起中继(bun) + 后端，等后端就绪后打开一个应用窗口内嵌网页控制台；
关闭窗口后按进程树清理中继与后端。全程无命令行窗口。

资源定位：打包模式 = exe 所在目录；源码模式 = 仓库根。
"""
import atexit
import ctypes
import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

CREATE_NO_WINDOW = 0x08000000
APP_TITLE = "Coyote in Cradle"
MUTEX_NAME = "CoyoteInCradleSingleInstance"
BACKEND_URL = "http://127.0.0.1:8000/api/state"

log = logging.getLogger("shell")

_procs: list[subprocess.Popen] = []
_mutex = None


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def setup_log(root: Path) -> None:
    (root / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=str(root / "logs" / "shell.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def message(text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, APP_TITLE, 0x10)
    except Exception:  # noqa: BLE001
        print(text)


def acquire_single_instance() -> bool:
    global _mutex
    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_bun(root: Path) -> Path | None:
    for p in (
        root / "bun.exe",
        Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "bun" / "bin" / "bun.exe",
        Path.home() / ".bun" / "bin" / "bun.exe",
        Path("C:/Program Files/Bun/bin/bun.exe"),
    ):
        if p.exists():
            return p
    return None


def spawn(cmd: list[str], cwd: Path, tag: str) -> subprocess.Popen:
    """无窗口子进程，stdout/stderr 追加到 logs/shell-<tag>.log。"""
    log_path = cwd / "logs" / f"shell-{tag}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    out = open(log_path, "ab", buffering=0)
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    _procs.append(p)
    log.info("%s 已启动 pid=%s cmd=%s", tag, p.pid, cmd)
    return p


def wait_backend_ready(timeout: float = 30.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BACKEND_URL, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def shutdown() -> None:
    """按进程树杀干净已启动的子进程（先停后杀）。"""
    for p in reversed(_procs):
        if p.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    creationflags=CREATE_NO_WINDOW,
                    timeout=15,
                )
            except Exception:  # noqa: BLE001
                log.exception("taskkill 失败 pid=%s", p.pid)
    _procs.clear()
    log.info("已全部退出")


def main() -> None:
    root = resource_root()
    setup_log(root)
    if not acquire_single_instance():
        message("Coyote in Cradle 已在运行。")
        return
    atexit.register(shutdown)
    try:
        # 1. 中继（9998 未占用才启动，开发环境可复用现有实例）
        if not port_in_use(9998):
            bun = find_bun(root)
            if bun is None:
                message("找不到 bun.exe（中继组件），请重新安装完整包。")
                return
            spawn([str(bun), "run", "v4-server.ts"], root / "relay", "relay")
        # 2. 后端（8000 未占用才启动）
        if not port_in_use(8000):
            if (root / "AI-for-Coyote.exe").exists():
                spawn([str(root / "AI-for-Coyote.exe")], root, "backend")
            else:
                spawn([sys.executable, "-m", "backend.main"], root, "backend")
        # 3. 等后端就绪
        if not wait_backend_ready():
            message("后端启动超时，请查看 logs\\app.log。")
            return
        # 4. 打开应用窗口
        import webview

        # 5. WebView2 需要一个目录来存储 cookie、localStorage 等，默认是用户临时目录，private_mode状态下每次启动都会清空，会导致状态丢失。
        storage_dir = root / "config" / "webview_storage"
        storage_dir.mkdir(exist_ok=True)

        try:
            window = webview.create_window(
                APP_TITLE,
                "http://127.0.0.1:8000",
                width=1440,
                height=900,
                min_size=(1100, 700),
            )
            webview.start(
                debug=False,
                storage_path=str(storage_dir),  
                private_mode=False,        
            )
        except webview.util.WebViewException as exc:
            log.exception("WebView 启动失败")
            message(
                "缺少 Edge WebView2 运行时。\n"
                "请安装：https://developer.microsoft.com/microsoft-edge/webview2/"
            )
    finally:
        shutdown()
        atexit.unregister(shutdown)


if __name__ == "__main__":
    main()
