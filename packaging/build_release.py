# -*- coding: utf-8 -*-
"""绿色免装发布包构建脚本。

组装：PyInstaller 打包的后端 exe + bun.exe 中继 + relay 源码 + 前端 dist
     + 配置模板 + content/pure 本体 + 启动器 + 说明，最后压 zip。

用法：
    python packaging/build_release.py            # 默认版本 0.1.0-beta
    python packaging/build_release.py 1.0.0

输出：
    build_release/AI-for-Coyote-v<版本>.zip
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 控制台编码可能不是 UTF-8（如 CI 的 cp1252），强制 UTF-8 输出，避免中文打印崩溃
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

VERSION = next((a for a in sys.argv[1:] if not a.startswith("--")), "0.1.0-beta")
CI = "--ci" in sys.argv  # CI 模式：用当前解释器（依赖已装好），不建 venv、不跑 npm
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build_release"
PKG = BUILD / f"Coyote-in-Cradle-v{VERSION}"


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


START_BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Coyote in Cradle v{version}
echo   仅供成年人、双方自愿的虚构角色扮演使用
echo   心脏病 / 心脏起搏器等健康风险人群请勿使用
echo   随时可长按空格 1 秒或页面急停按钮中断
echo ============================================
timeout /t 2 /nobreak >nul

if exist "%~dp0bun.exe" (set "BUN=%~dp0bun.exe") else (where bun >nul 2>nul && set "BUN=bun")
if not defined BUN (
  echo [错误] 找不到 bun.exe，中继无法启动
  pause
  exit /b 1
)

start "AI-for-Coyote 中继" /min cmd /c ""%BUN%" run "%~dp0relay\\v4-server.ts""
start "AI-for-Coyote" /d "%~dp0" "%~dp0AI-for-Coyote.exe"

timeout /t 3 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo 已启动。关闭两个命令窗口即停止程序。
pause
"""

README_TXT = """Coyote in Cradle v{version}（绿色免装版）
========================================

仅供成年人、双方自愿的虚构角色扮演使用。
健康风险人群（心脏病、心脏起搏器等）请勿使用。

【启动（推荐）】
双击 Coyote-in-Cradle.exe：静默启动中继 + 主程序，弹出应用窗口；
关闭窗口即全部退出，无命令行窗口。

【启动（备用）】
双击 start.bat：自动启动中继 + 主程序，并打开浏览器 http://127.0.0.1:8000

【配置 AI】
网页「设置 → AI 模型配置」填 API Key / 地址 / 模型名，
点「测试连接」验证后「保存并生效」（无需重启）。
也可手动复制 config\\config.example.yaml 为 config.yaml 修改。

【配对郊狼】
手机连与电脑相同的 Wi-Fi，用 DG-LAB 4.0 App 扫页面右侧二维码。

【急停】
页面大红按钮，或页面不在输入框时长按空格 1 秒（松手取消）。

【角色与内容】
本包内置「纯爱体验版」试玩内容，开箱即可体验。
正式角色稿（触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后）属 R18 内容，不随本包分发：
到发布渠道下载「Coyote-in-Cradle-DLC-zh-*.zip」，在程序侧边栏「内容 / 语言包 →
选择 zip 并安装」一键导入（或解压合并 content/roles 到本目录后重启）。
英文稿另见「Coyote-in-Cradle-DLC-en-*.zip」，安装后聊天栏 ZH / EN 一键切换。
（地牢玩法重做中，暂不随版本发布。）

【许可】
本软件为作者原创的专有软件（All Rights Reserved），未授权任何渠道转载、倒卖与二次分发。
中继基于 dglab-websocket-server（GPL-3.0），作为独立第三方组件分发，见 relay\\LICENSE。
"""


def main() -> None:
    if CI:
        py = Path(sys.executable)
        pyinstaller = None
    else:
        step("1/6 构建前端")
        run(["npm.cmd", "run", "build"], cwd=ROOT / "frontend")

        step("2/6 准备构建 venv 与依赖（首次较慢）")
        venv = BUILD / "venv"
        if not (venv / "Scripts" / "python.exe").exists():
            run([sys.executable, "-m", "venv", str(venv)])
        py = venv / "Scripts" / "python.exe"
        # 本地构建：阻断代理（系统 WinINET 可能残留死代理 127.0.0.1:xxxx），走清华镜像
        env = dict(os.environ)
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
            env.pop(k, None)
        # 显式置空 + no_proxy=*：阻止 pip 回退读取注册表里的系统代理
        env["http_proxy"] = ""
        env["https_proxy"] = ""
        env["no_proxy"] = "*"
        env["NO_PROXY"] = "*"
        pip = [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check",
               "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
               "--timeout", "30", "--retries", "5"]
        run(pip + ["-r", str(ROOT / "requirements.txt"), "pyinstaller", "opencv-python", "numpy", "pywebview"], env=env)
        pyinstaller = venv / "Scripts" / "pyinstaller.exe"

    # pyinstaller 可能在 python 同目录（venv）或 Scripts\ 子目录（setup-python 布局），再从 PATH 兜底
    if pyinstaller is None:
        pyinstaller = next(
            (
                p
                for p in (
                    py.parent / "pyinstaller.exe",
                    py.parent / "Scripts" / "pyinstaller.exe",
                )
                if p.exists()
            ),
            None,
        )
        if pyinstaller is None:
            found = shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")
            pyinstaller = Path(found) if found else None
    if pyinstaller is None:
        raise SystemExit("找不到 pyinstaller：请先 pip install pyinstaller")

    step("3/6 PyInstaller 打包后端")
    run(
        [
            str(pyinstaller),
            "--noconfirm", "--clean", "--onefile",
            "--name", "AI-for-Coyote",
            # 后端 exe 不配图标：只有壳（Coyote-in-Cradle.exe）带图标，避免误导用户点错
            "--distpath", str(BUILD / "dist"),
            "--workpath", str(BUILD / "pyi_work"),
            "--specpath", str(BUILD),
            "--exclude-module", "faster_whisper",
            "--exclude-module", "torch",
            "--exclude-module", "tensorflow",
            "--hidden-import", "uvicorn.logging",
            "--hidden-import", "uvicorn.loops.auto",
            "--hidden-import", "uvicorn.protocols.http.auto",
            "--hidden-import", "uvicorn.protocols.websockets.auto",
            "--hidden-import", "uvicorn.lifespan.on",
            "--hidden-import", "multipart",
            "--hidden-import", "multipart.multipart",
            str(ROOT / "run_app.py"),
        ]
    )

    step("3.5/7 PyInstaller 打包桌面壳")
    run(
        [
            str(pyinstaller),
            "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "Coyote-in-Cradle",
            "--icon", str(ROOT / "desktop" / "app.ico"),
            "--distpath", str(BUILD / "dist"),
            "--workpath", str(BUILD / "pyi_work_shell"),
            "--specpath", str(BUILD),
            "--collect-all", "webview",
            "--collect-all", "pywebview",
            str(ROOT / "desktop" / "shell.py"),
        ]
    )

    step("4/7 组装发布目录")
    if PKG.exists():
        shutil.rmtree(PKG)
    (PKG / "config").mkdir(parents=True)
    # 内容红线（2026-09-03 用户定版）：主包 content/ 只内置「纯爱体验版」试玩（CN），
    # 开箱即聊；5 个正式角色稿与地牢主题包（R18）一律不进主包，只随 DLC 大包由用户导入。
    (PKG / "content").mkdir(parents=True)
    pure = ROOT / "content" / "pure"
    if pure.exists():
        shutil.copytree(pure, PKG / "content" / "pure",
                        ignore=shutil.ignore_patterns("*-EN.md"))  # EN 稿走 DLC-en
    else:
        print("[警告] 缺少 content/pure：主包将无内置试玩内容", flush=True)
    (PKG / "content" / "安装内容包说明.txt").write_text(
        "本目录已内置「纯爱体验版」试玩内容（content/pure）。\n"
        "正式角色稿（触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后）属 R18 内容，不随主包分发："
        "请在程序侧边栏「内容 / 语言包」选择 DLC zh 大包 zip 一键安装，"
        "或把解压出的 content/roles 合并进本目录后重启。\n",
        encoding="utf-8",
    )
    shutil.copy2(BUILD / "dist" / "AI-for-Coyote.exe", PKG / "AI-for-Coyote.exe")
    shutil.copy2(BUILD / "dist" / "Coyote-in-Cradle.exe", PKG / "Coyote-in-Cradle.exe")
    shutil.copy2(ROOT / "desktop" / "setup.ico", PKG / "setup.ico")
    bun = next(
        (
            p
            for p in (
                Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "bun" / "bin" / "bun.exe",
                Path.home() / ".bun" / "bin" / "bun.exe",
                Path("C:/Program Files/Bun/bin/bun.exe"),
            )
            if p.exists()
        ),
        None,
    )
    if bun is None:
        found = shutil.which("bun") or shutil.which("bun.exe")
        bun = Path(found) if found else None
    if bun is None:
        raise SystemExit("找不到 bun.exe：请先 npm install -g bun 或安装 Bun")
    shutil.copy2(bun, PKG / "bun.exe")
    shutil.copytree(
        ROOT / "relay", PKG / "relay",
        ignore=shutil.ignore_patterns("node_modules", ".env", "*.log"),
    )
    for name in ("config.example.yaml", "character.example.yaml", "waveforms.yaml"):
        shutil.copy2(ROOT / "config" / name, PKG / "config" / name)
    # 注意：content/pure、content/roles、content/pack（R18）一律不拷贝——红线见上。
    # 老版本曾把纯爱/角色/地牢内容打进主包（v1.1.6 之前），已按要求移除。
    shutil.copytree(ROOT / "frontend" / "dist", PKG / "frontend" / "dist")
    shutil.copy2(ROOT / "LICENSE", PKG / "LICENSE")
    (PKG / "start.bat").write_text(START_BAT.format(version=VERSION), encoding="utf-8")
    (PKG / "说明.txt").write_text(README_TXT.format(version=VERSION), encoding="utf-8")
    (PKG / "version.txt").write_text(VERSION, encoding="utf-8")

    step("5/7 压缩")
    zip_path = BUILD / f"Coyote-in-Cradle-v{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", PKG.parent, PKG.name)

    step("6/7 生成安装器脚本")
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    iss = (
        iss.replace("{version}", VERSION)
        .replace("{pkgdir}", str(PKG))
        .replace("{outdir}", str(BUILD))
    )
    (BUILD / "installer.iss").write_text(iss, encoding="utf-8")

    step(f"7/7 完成：{zip_path}（{zip_path.stat().st_size / 1024 / 1024:.1f} MB）")


if __name__ == "__main__":
    main()
