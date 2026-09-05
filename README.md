<a id="top"></a>

<div align="center">

<h1>Coyote in Cradle</h1>
<p><strong>AI 角色扮演 × 郊狼（DG-Lab）</strong></p>

<p>
  <a href="https://github.com/indhg/AI-for-Coyote/releases/latest"><img alt="Release" src="https://img.shields.io/badge/下载-Windows-blue?style=flat-square&logo=windows"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-green?style=flat-square"></a>
  <a href="https://ifdian.net/a/cinnanirch"><img alt="Afdian" src="https://img.shields.io/badge/爱发电-求求打赏🙏-946ce6?style=flat-square"></a>
</p>

<p>
  <a href="#中文">中文</a> · <a href="#english">English</a>
</p>

</div>

---

<a id="中文"></a>

## 🇨🇳 中文

## ⬇️ 下载导航

| 端 | 下载 | 说明 |
|---|---|---|
| 🖥️ **PC（Windows）** | 👉 <https://github.com/indhg/AI-for-Coyote/releases/latest> | `Coyote-in-Cradle-setup-v*.exe`（安装版）或免装 zip，解压即用；用法见下方「快速开始」 |
| 📱 **安卓（Android）** | 👉 <https://github.com/indhg/Coyote-in-Cradle-Android/releases/latest> | `Coyote-in-Cradle-*-release.apk`；独立 App，BLE 直连郊狼，无需 PC 与中继 |
| 🧩 **DLC 内容（R18，自行导入）** | 👉 <https://github.com/indhg/AI-for-Coyote-DLC/releases> | 正式角色稿 zh / en 大包，不随主包分发；下载后程序内「内容 / 语言包」一键导入 |

### ☕ 自愿打赏

若本项目对你有帮助，欢迎在爱发电自愿支持作者喵：

👉 **<https://ifdian.net/a/cinnanirch>**

---

## ✨ 它能做什么

| | 能力 | 说明 |
|---|---|---|
| 🎭 | **AI 角色闭环** | 每轮按「观察 → 描写 → 动作 → 发言」推进；回复为严格 JSON，台词与设备指令分离 |
| 👁️🎤 | **摄像头 / 麦克风观察** | 画面变暗或无人 → 角色逐渐不耐烦再到暴怒；呻吟分级：普通呻吟小幅加码、惨叫立即收敛 |
| 🤖 | **自动运行（Autopilot）** | 不需要打字，按间隔自动循环观察-描写-动作-发言；传感器跟随启停 |
| 🎛️ | **手动控制台** | A/B 双通道独立控制：保持强度、增减、清除、24 种内置波形（可循环）；通道开关与强度上限（1–200，默认 100） |
| 🗺️ | **紫金地牢 demo** | 引擎随主程序；剧情包走 DLC（zijin-demo zip） |
| 🌐 | **中英一键切换** | 聊天栏上方的 ZH / EN 入口；界面与角色内容同步切英文 |
| 🛡️ | **多层安全** | 强度上限、单指令步长 ≤40、中继 / App 断连自动清零、急停（按钮 / 长按空格 1 秒） |
| 🧩 | **内容即装即用** | 内置体验版（中英）；正式角色经 DLC 大包在程序内一键导入（见「内容清单」） |
| 📦 | **随开随用** | Windows 安装包 / 免装包；自动更新检测、公告浮窗、首次使用引导 |

---

## 🧩 内容清单

内容分两档：

- **随包内置**（开箱即玩）：体验版（Trial）——触手 · 纯爱向试玩内容，含中英文稿（聊天栏 ZH / EN 切换即用英文）；
- **R18 正式内容**（不随主包分发，需自行导入）：正式角色稿经 **DLC 大包**导入后出现在角色卡。

| 内容 | 分发形态 | 语言 |
|---|---|---|
| 体验版（触手 · 纯爱向） | ✅ 内置主包（content/pure） | 中文 + 英文 |
| 触手 / 品评会 / 哥布林 / 史莱姆 / 蛛后（正式角色稿） | DLC-zh 大包（R18，自行导入） | 中文 |
| 上述正式角色稿的英文版 | DLC-en 大包（自行导入） | 英文 |

> 正式角色稿（`content/roles`）与地牢主题包属 R18 内容：**主仓库与主发布包一律不含**，请通过作者渠道的 DLC 大包获得并自行导入。

### 安装 DLC（正式角色，R18）

1. 到 **AI-for-Coyote-DLC** 仓库 Releases 下载 `Coyote-in-Cradle-DLC-zh-*.zip`（中文正式角色）或 `Coyote-in-Cradle-DLC-en-*.zip`（英文稿）：
   👉 **<https://github.com/indhg/AI-for-Coyote-DLC/releases>**
2. 打开程序 → 侧边栏底部 **「内容 / 语言包」→ 选择 zip 并安装**，自动合并进 `content/` 即时生效；
3. 或手动解压，把 zip 内 `content/…` 合并到程序目录的 `content/` 后重启。

> 紫金地牢 demo：引擎在主程序；剧情文本包请从 DLC 仓库导入（Coyote-in-Cradle-DLC-zijin-demo.zip）。

**运行链路**

```text
桌面窗口 / 浏览器网页 ⇄ Python 主程序（FastAPI，8000）
        ⇄ dglab-websocket-server v4 中继（Bun，9998）
        ⇄ DG-LAB 4.0 App（手机，扫码配对） ⇄ 郊狼主机（A/B 通道）

主程序横切：摄像头观察 · 麦克风分级 · LLM（OpenAI 兼容） · 安全层 · 地牢运行时
```

---

## 🚀 快速开始（Windows）

### 方式 A：安装包（推荐）

1. 到 [Releases](https://github.com/indhg/AI-for-Coyote/releases/latest) 下载 `Coyote-in-Cradle-setup-v*.exe`；
2. 双击安装，打开桌面图标「Coyote in Cradle」；
3. 免命令行、免浏览器——一个应用窗口，关窗即全部退出。

> 不想安装？下载免装 zip，解压后双击 `Coyote-in-Cradle.exe`（备用 `start.bat`）。

### 方式 B：源码运行

<details>
<summary><b>环境要求</b></summary>

- Python 3.10+（主程序）
- [Bun](https://bun.sh)（中继服务；`npm install -g bun`）
- Node.js 18+（仅首次构建前端需要）
- 可选：摄像头 `pip install opencv-python`；麦克风 `pip install sounddevice numpy`（不装则对应功能自动禁用）

</details>

**1. 装依赖 + 构建前端**

```bat
pip install -r requirements.txt
cd relay & bun install
cd ..\frontend & npm install & npm run build
```

> 主程序通过 FastAPI 直接托管 `frontend/dist`，源码运行**必须先构建一次前端**。

**2. 配置**

```bat
copy config\config.example.yaml config\config.yaml
copy config\character.example.yaml config\character.yaml
```

- `config/config.yaml`：填 `llm.api_key`（或环境变量 `DGLAB_LLM_API_KEY`）与模型 Base URL；联调阶段 `dry_run: true`，接真机再改 `false`；
- 更省事：启动后网页 **设置 → AI 模型配置** 里直接填，点「测试连接」验证、「保存并生效」即时切换，无需重启；
- `config/character.yaml`：角色清单与切换；`config/device_channels.yaml`：通道配件映射（首次运行自动生成）。

**3. 启动**

双击 `start.bat`（自动：起中继 → 起主程序 → 开浏览器），或手动：

```bat
cd relay & bun run v4-server.ts        REM 窗口 1：中继（9998）
python -m backend.main                 REM 窗口 2：主程序（8000）
```

浏览器打开 <http://127.0.0.1:8000>。

**4. 配对郊狼（手机 + 局域网）**

1. 手机连接**与电脑同一个 Wi-Fi**；
2. DG-LAB 4.0 App → Socket V4 控制入口 → 扫网页右侧二维码；
3. App 内蓝牙连接郊狼主机，页面状态变为「已配对」；
4. 扫不上？检查防火墙放行 9998（管理员运行）：
   `netsh advfirewall firewall add rule name="dglab-relay" dir=in action=allow protocol=TCP localport=9998`

---

## 🎛️ 使用要点

- **聊天**：左侧与 AI 对话；指令先校验后执行，被拒原因（如超上限、通道关闭、急停中）会以 ✖ 卡片回显，中英文随界面切换。
- **手动控制**：右侧每通道 保持强度 / 增减 / 清除 / 波形（可循环）；配件名与位置可改（敲回车生效）。
- **自动运行**：聊天栏顶部开关；摄像头 / 麦克风跟随启停。
- **急停**：大红按钮，或页面不在输入框时**长按空格 1 秒**（松手取消）；急停 = 全通道清零 + 清波形 + 暂停 AI，点「解除急停」恢复。
- **安全约定**：不设安全词口令，靠急停 + 「AI 察觉连续痛苦表达自动收敛」兜底；实机前务必先 `dry_run` 联调并核对强度基准。

---

## 🛡️ 安全设计

一切来源（AI / 手动 / 地牢反馈）的指令都经过 `backend/safety.py`：

1. 每通道独立强度上限（默认 100），AI / 手动都超不过；
2. 单条指令强度变化 ≤ 40，防跳变；
3. 波形 / 临时强度到点自动归零；持续波形仅在明确持有命令下保持；
4. 设备过热 → 该通道上限临时降为 20；
5. 中继 / App 断开 → 自动清零；
6. 急停 = 清零 + 清波形 + 暂停循环；
7. 使用注意：电极不可跨心脏、不可置于颈部以上；不同配件分别调低对应上限。

---

## 🤖 AI 指令协议

模型每次回复为严格 JSON：

```json
{
  "line": "角色台词（原样显示）",
  "actions": [
    { "op": "temp_strength", "channel": "A", "value": 60, "duration_s": 3 },
    { "op": "add_strength",  "channel": "B", "delta": 10 },
    { "op": "pulse",         "channel": "A", "pattern": "短促连击", "duration_s": 2 },
    { "op": "clear",         "channel": "B" },
    { "op": "stop" }
  ]
}
```

波形库在 `config/waveforms.yaml`（`presets` 中文名 → 波形映射，`custom` 为官方波形 64 帧数据）。操作代码名不变，界面显示名中英文随语言切换（详见英文版 §AI 指令协议）。

---

## ❓ 常见问题

- **报「API Key 无效」**：官方与中转站密钥不通用——Base URL 与密钥要配套（官方填 `https://api.deepseek.com`），先用设置页「测试连接」验证。
- **「服务器返回了网页」/ 测试连接过但对话抽风**：Base URL 填成了网页地址；或中转站不支持 JSON 模式 → 设置里**关掉「JSON 模式」**（程序自动兜底解析）。
- **麦克风「未运行 / 启动中」**：先开自动运行；按钮变橙色时悬停看原因（常见：台式机无麦克风、系统权限被禁）。
- **没有二维码 / 配不上**：确认中继在跑（9998 端口有进程、`start.bat` 窗口没关），再看防火墙。
- **语言切了没变化**：角色无英文稿时保持中文是设计（会显示对应提示）；内容语言与界面语言走同一个开关。

---

## 🗂️ 目录结构

```text
AI-for-Coyote\
├── backend\              Python 主程序（FastAPI：控制 / 安全层 safety / 游戏闭环 game_loop /
│                         LLM / 中继客户端 / 设备波形 / 摄像头 / 麦克风 / 地牢 dungeon / UI 英文映射 ui_en）
├── frontend\             React 19 + TS + Vite + Tailwind v4 控制台（i18n 中英切换；dist\ 由后端托管）
├── desktop\              桌面壳（pywebview 应用窗口；shell.py）
├── packaging\            打包脚本（免装 zip + Inno Setup 安装器）
├── relay\                dglab-websocket-server（Bun，v4 端口 9998，GPL-3.0 第三方组件）
├── config\               示例配置 / waveforms.yaml 波形库
├── content\              本地内容目录（**不入库、不进主发布包**）：pure\ 纯爱体验版（CN+EN，随主包内置）；roles\ 正式角色稿（R18，经 DLC-zh 导入后出现）；pack\ 地牢素材（玩法重做中）
├── logs\                 运行日志
└── start.bat             一键启动
```

---

## 🧑‍💻 前端开发

- 日常使用：后端托管 `frontend/dist`——改完前端先 `npm run build`；
- 开发模式：`frontend\` 下 `npm run dev`（Vite 代理 `/api` 与 `/ws` 到 8000，浏览器开 5173）；
- 文案体系：界面文案全部收敛到 `frontend/src/i18n.ts`（中英词典 + `t()`/`useT()`），新增可见文案请走词典而非硬编码。

---

## 🗺️ 路线

**进行中**

- 紫金地牢 demo 已可玩（引擎主仓 + 剧情 DLC）；继续打磨中；
- DLC 内容渠道运营（zh / en 大包随主版本同步更新）。

**计划**

- 语音指令（ASR）可选开关评估；
- 郊狼 2.0（脉冲主机 V2 / D-LAB ESTIM01）适配评估；
- 更多角色与地牢主题包。

---

## ⚠️ 免责声明

本项目仅供**成年用户**在**自愿、知情、同意**的前提下用于个人娱乐。请：

- 遵守所在地区法律法规；
- 评估自身身体状况——心脏病、心脏起搏器等风险人群请勿使用；
- 控制强度与时长，随时可用急停中断（长按空格 1 秒）；
- 使用本项目造成的一切后果由使用者自行承担。

## 📜 许可证

- 本仓库为作者原创，采用 **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**（见 [LICENSE](LICENSE)）：可免费使用、修改与分享，**须署名**，**禁止商业性使用**；完整条款以 LICENSE 内法律文本为准；
- `relay/` 源自 [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)（GPL-3.0），作为独立第三方组件随包分发（见 `relay/LICENSE`），不受本仓库 CC 条款约束；
- 角色稿与主题包内容版权归作者，仅通过作者渠道获得并自行导入；本 GitHub 仓库托管代码主体，不含任何内容文件。

## 🙏 致谢与联系

- 作者推特：<https://x.com/cinnanirch>（支持请去点个关注喵～）
- **自愿打赏（爱发电）**：👉 <https://ifdian.net/a/cinnanirch>  
  完全自愿；**不解锁任何功能 / 更新 / DLC**，软件与内容仍按许可证免费使用与分享。打赏用于作者维护、真机测试与基础设施等（感谢你的支持喵～）
- 中继协议与上游：[dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)
- 问题反馈 / 建议：GitHub [Issues](https://github.com/indhg/AI-for-Coyote/issues) / [Discussions](https://github.com/indhg/AI-for-Coyote/discussions)

[⬆ 回到顶部](#top)

---

<a id="english"></a>

# 🇬🇧 English

## ⬇️ Download hub

| Platform | Download | Notes |
|---|---|---|
| 🖥️ **PC (Windows)** | 👉 <https://github.com/indhg/AI-for-Coyote/releases/latest> | `Coyote-in-Cradle-setup-v*.exe`（installer）or the portable zip; see “Quick start” below |
| 📱 **Android** | 👉 <https://github.com/indhg/Coyote-in-Cradle-Android/releases/latest> | `Coyote-in-Cradle-*-release.apk`; standalone app, BLE direct to the Coyote — no PC or relay needed |
| 🧩 **DLC content (R18, install yourself)** | 👉 <https://github.com/indhg/AI-for-Coyote-DLC/releases> | Official-character zh / en packs, not shipped with the main build; import in-app via “Content / language packs” |

### ☕ Voluntary tips

If this project helps you, you can optionally support the author on Afdian / 爱发电:

👉 **<https://ifdian.net/a/cinnanirch>**

---

> **In one sentence:** an AI role-playing system in which the character watches through your camera, listens through your microphone, and drives a Coyote（DG-Lab）device in real time — a full "observe → describe → act → speak" loop inside a **local web console**.
>
> **What makes it more than a chatbot:** the actions are real. The model emits structured device commands that pass through `backend/safety.py` first（intensity caps / step limits / overheat protection / auto-clear on disconnect）— only validated commands touch the hardware.

### Three promises

- **Your data stays local** — apart from the model API you choose, everything runs on your own machine;
- **No model lock-in** — any OpenAI-compatible endpoint works（DeepSeek, relays, local servers）; fill in the Base URL from the UI;
- **Bilingual out of the box** — one ZH / EN switch flips both the interface and the character content.

---

## ✨ Highlights

| | Feature | What it does |
|---|---|---|
| 🎭 | **AI role loop** | Each round: observe → describe → act → speak; replies are strict JSON, dialogue separated from device commands |
| 👁️🎤 | **Camera / mic sensing** | Dark or empty frame → impatience, then anger; moans are graded — ordinary ones nudge intensity up, screams pull it straight down |
| 🤖 | **Autopilot** | Runs the whole loop on an interval without typing; sensors follow it |
| 🎛️ | **Manual console** | Independent A/B channels: hold, adjust, clear, 24 built-in waveforms（loopable）; per-channel on/off and caps（1–200, default 100） |
| 🗺️ | **Dungeon mode** | Being rebuilt — not shipped with current releases |
| 🌐 | **One-tap bilingual UI** | ZH / EN switch above the chat panel; the interface and character content switch together |
| 🛡️ | **Layered safety** | Caps, ≤40 step changes, overheat limit drop, auto-clear on disconnect, emergency stop（button / hold Space for 1s） |
| 🧩 | **Content, ready to load** | Trial version built in (ZH + EN); official characters installed in-app from DLC packs (see below) |
| 📦 | **Open-and-play** | Windows installer / portable builds; update checks, announcement pop-ups, first-run onboarding |

---

## 🧩 Content

Content ships in two tiers:

- **Built into the main package**（ready to play）: the Trial version — Tentacle · pure-love sample, with both Chinese and English scripts（use the ZH / EN switch above the chat panel）;
- **R18 official content**（not shipped; install it yourself）: official character scripts arrive via **DLC packs** and appear on the character card once installed.

| Content | Distribution | Language |
|---|---|---|
| Trial（Tentacle · pure-love sample） | ✅ Built in（content/pure） | Chinese + English |
| Tentacle / Appraisal / Goblin / Slime / Arachne（official scripts） | DLC-zh pack（R18, install it yourself） | Chinese |
| English versions of the official scripts above | DLC-en pack（install it yourself） | English |

> Official scripts（`content/roles`）and dungeon theme packs are R18 material: **neither this repo nor the main release contains them** — get them from the author's DLC packs and install them yourself.

### Installing DLC（official characters, R18）

1. Grab `Coyote-in-Cradle-DLC-zh-*.zip`（Chinese official characters）or `Coyote-in-Cradle-DLC-en-*.zip`（English scripts）from the **AI-for-Coyote-DLC** repo Releases:
   👉 **<https://github.com/indhg/AI-for-Coyote-DLC/releases>**
2. Open the app → sidebar footer **「Content / language packs」→ pick the zip and install** — files are merged into `content/` and take effect immediately;
3. Or unzip manually and merge the `content/…` folder into the app's `content/`, then restart.

> Violet Dungeon demo: engine ships with the app; story pack installs from the DLC repo (Coyote-in-Cradle-DLC-zijin-demo.zip).

**Runtime chain**

```text
Desktop window / browser ⇄ Python app（FastAPI, 8000）
        ⇄ dglab-websocket-server v4 relay（Bun, 9998）
        ⇄ DG-LAB 4.0 App（phone, scan-to-pair） ⇄ Coyote device（A/B）

The main program also owns: camera sensing · mic grading · LLM（OpenAI-compatible）· safety layer · dungeon runtime
```

---

## 🚀 Quick start（Windows）

### Option A — Installer（recommended）

1. Grab `Coyote-in-Cradle-setup-v*.exe` from [Releases](https://github.com/indhg/AI-for-Coyote/releases/latest);
2. Install and open the “Coyote in Cradle” shortcut;
3. No command line, no browser — one app window; closing it exits everything.

> Prefer portable? Download the zip, unzip, and double-click `Coyote-in-Cradle.exe`（fallback `start.bat`）.

### Option B — Run from source

<details>
<summary><b>Requirements</b></summary>

- Python 3.10+（main program）
- [Bun](https://bun.sh)（relay; `npm install -g bun`）
- Node.js 18+（frontend build only）
- Optional: camera `pip install opencv-python`; mic `pip install sounddevice numpy`（features auto-disable when missing）

</details>

**1. Install + build once**

```bat
pip install -r requirements.txt
cd relay & bun install
cd ..\frontend & npm install & npm run build
```

> The backend serves `frontend/dist` directly — you **must build the frontend once** when running from source.

**2. Configure**

```bat
copy config\config.example.yaml config\config.yaml
copy config\character.example.yaml config\character.yaml
```

- `config/config.yaml`: set `llm.api_key`（or `DGLAB_LLM_API_KEY`）and the Base URL; keep `dry_run: true` while testing, switch to `false` for a real device;
- Easier: use **Settings → AI model** in the UI — “Test Connection”, then “Save & Apply” takes effect immediately;
- `config/character.yaml`: roles; `config/device_channels.yaml`: channel-to-accessory mapping（auto-generated on first run）.

**3. Start**

Double-click `start.bat`, or manually:

```bat
cd relay & bun run v4-server.ts        REM Window 1: relay（9998）
python -m backend.main                 REM Window 2: main program（8000）
```

Open <http://127.0.0.1:8000>.

**4. Pair the Coyote（phone + LAN）**

1. Connect the phone to the **same Wi-Fi** as the PC;
2. DG-LAB 4.0 App → Socket V4 entry → scan the QR code on the page;
3. Connect the Coyote over Bluetooth inside the App; the page shows “Paired”;
4. Can't scan? Allow port 9998 through the firewall（as admin）:
   `netsh advfirewall firewall add rule name="dglab-relay" dir=in action=allow protocol=TCP localport=9998`

---

## 🎛️ Usage notes

- **Chat**: dialogue on the left; commands are validated first — rejected reasons（over cap, channel off, E-Stop…）come back as ✖ cards, bilingual with the UI.
- **Manual control**: hold / adjust / clear / waveforms per channel; rename accessories and locations（press Enter to apply）.
- **Autopilot**: switch at the top of the chat panel; camera / mic follow it.
- **E-Stop**: the big red button, or **hold Space for 1 second** while the page is not focused on an input（release to cancel）. It clears every channel, clears waveforms, and pauses the AI loop.
- **No safe-word password**: safety rests on E-Stop plus the AI's automatic convergence after repeated distress signals. Always `dry_run` first and confirm baselines before a real session.

## 🛡️ Safety design

Every command — from AI, manual control, or dungeon feedback — goes through `backend/safety.py`:

1. Independent per-channel intensity caps（default 100）that no source can exceed;
2. Intensity changes per command ≤ 40（no jumps）;
3. Waveforms / temporary intensity auto-zero when done;
4. Overheating drops that channel's cap to 20 temporarily;
5. Relay / App disconnect clears everything;
6. E-Stop = clear + zero + pause;
7. Never place electrodes across the heart or above the neck; lower caps per accessory.

## 🤖 AI command protocol

```json
{
  "line": "Character dialogue（shown as-is）",
  "actions": [
    { "op": "temp_strength", "channel": "A", "value": 60, "duration_s": 3 },
    { "op": "add_strength",  "channel": "B", "delta": 10 },
    { "op": "pulse",         "channel": "A", "pattern": "短促连击", "duration_s": 2 },
    { "op": "clear",         "channel": "B" },
    { "op": "stop" }
  ]
}
```

Command names never change; their display labels on the chips are localized（`backend/ui_en.py` + the frontend dictionary）.

## ❓ FAQ

- **“Invalid API Key”**: official and relay keys are not interchangeable — Base URL and key must match（official: `https://api.deepseek.com`）; use “Test Connection” first.
- **“The server returned a webpage” / weird chats**: the Base URL is a web page, not an API endpoint; or the relay lacks JSON mode — turn **JSON Mode off** in Settings（the app falls back automatically）.
- **Mic shows “Not running / Starting”**: enable autopilot first; hover the orange button for the reason.
- **No QR code / can't pair**: make sure the relay is up（something listening on 9998）and check the firewall.
- **Language switch has no effect**: characters without an EN script stay Chinese by design（the UI says so）; one switch drives both interface and content language.

## 🗂️ Directory layout

```text
AI-for-Coyote\
├── backend\              Python main program（FastAPI: control / safety / game_loop / LLM /
│                         relay client / waveforms / camera / audio / dungeon / ui_en）
├── frontend\             React 19 + TS + Vite + Tailwind v4 console（i18n; dist\ served by backend）
├── desktop\              Desktop shell（pywebview; shell.py）
├── packaging\            Packaging scripts（portable zip + Inno Setup installer）
├── relay\                dglab-websocket-server（Bun, v4 on 9998; GPL-3.0 third-party）
├── config\               Example configs + waveforms.yaml
├── content\               Local content dir（**not in this repo, not in the main release**）: pure\ Trial（CN+EN, shipped）; roles\ official scripts（R18, appear after installing DLC-zh）; pack\ dungeon material（being rebuilt）
├── logs\                 Runtime logs
└── start.bat             One-click startup
```

## 🧑‍💻 Frontend development

- Production: the backend serves `frontend\dist` — run `npm run build` after changes;
- Dev: `npm run dev` under `frontend\`（Vite proxies `/api` and `/ws` to 8000; open 5173）;
- i18n: all visible strings live in `frontend/src/i18n.ts`（ZH/EN dictionary + `t()`/`useT()`）— add new strings there, never hard-code.

## 🗺️ Roadmap

**In progress**

- Violet Dungeon demo playable (engine in main repo + story DLC); still being polished;
- DLC channel operation（zh / en packs stay in sync with main releases）.

**Planned**

- Optional ASR（voice-command extraction）;
- Coyote 2.0（Pulse Host V2 / D-LAB ESTIM01）evaluation;
- More characters and dungeon theme packs.

## ⚠️ Disclaimer

For **adults only**, for personal entertainment under **voluntary, informed, and consensual** conditions. Follow local law; do not use with heart disease, pacemakers, or similar risks; control intensity and duration and use the E-Stop freely（hold Space for 1s）; all consequences of use are the user's own.

## 📜 License

- The repository is the author's original work under **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)** (see [LICENSE](LICENSE)): you may use, modify and share it for free with **attribution**, for **NonCommercial** purposes only. The LICENSE file contains the full legal text;
- `relay/` originates from [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)（GPL-3.0）, shipped as an independent third-party component（`relay/LICENSE`）and is not covered by this repo's CC terms;
- Character scripts and theme-pack content belong to the author and are obtained only through the author's channels, then imported by yourself; this GitHub repo hosts the code base and contains no content files.

## 🙏 Thanks & contact

- Author on X（Twitter）: <https://x.com/cinnanirch>
- **Voluntary tips (Afdian / 爱发电)**: 👉 <https://ifdian.net/a/cinnanirch>  
  Entirely optional — **does not unlock features, updates, or DLC**. The software stays free to use and share under the license. Tips help with maintenance, device testing, and infrastructure. Thank you!
- Relay protocol & upstream: [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)
- Bugs / ideas: GitHub [Issues](https://github.com/indhg/AI-for-Coyote/issues) / [Discussions](https://github.com/indhg/AI-for-Coyote/discussions)

[⬆ Back to top](#top)
