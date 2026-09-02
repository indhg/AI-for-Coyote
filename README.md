<a id="top"></a>

<div align="center">
  <h1>Coyote in Cradle</h1>
  <p>郊狼 × AI 角色扮演系统</p>
  <p><a href="#中文">中文</a> · <a href="#english">English</a></p>
</div>

<a id="中文"></a>

## 中文

> **一句话介绍**：AI 扮演角色，通过摄像头观察、麦克风听声，实时控制郊狼（DG-Lab）设备。

当前主题：**触手**（纯爱／调教两档）、**品评会**（调教档，DLC）；档位显示名为纯爱／调教／凌辱（=轻／中／重），更多角色通过 DLC 机制接入。

## ⬇️ 下载安装包（Windows）

下载请点这里喵：

👉 <https://github.com/indhg/AI-for-Coyote/releases/latest>

**本项目为作者原创的专有软件（All Rights Reserved），未授权任何渠道转载、倒卖与二次分发，请认准官方发布渠道。** 作者推特主页欢迎来支持喵～<https://x.com/cinnanirch>

## 📦 相关仓库

本项目是**多端应用**。除本仓库（PC 端主仓库）外，还有两个配套仓库：

| 仓库 | 地址 | 说明 |
|---|---|---|
| 🧪 **DLC 拓展仓库** | [indhg/AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) | 18+ 拓展内容（当前：DLC1-触手-调教、DLC2-品评会-调教） |
| 📱 **安卓端** | [indhg/Coyote-in-Cradle-Android](https://github.com/indhg/Coyote-in-Cradle-Android) | 无需电脑，蓝牙直连郊狼 3.0（BLE 直连，无需中继） |

依赖 **郊狼 + dglab-websocket-server 的 Socket 接口**。

```text
桌面应用窗口（或浏览器 Web 页面） ⇄ Python 主程序（FastAPI） ⇄ dglab-websocket-server v4（Bun） ⇄ DG-LAB 4.0 App（手机） ⇄ 郊狼主机（A／B 通道）
                     │
                     └─ OpenAI 兼容模型（角色台词 + 结构化设备指令 + 摄像头／麦克风观察）
```

## ✨ 功能一览

### AI 观察与角色推进

AI 每轮按「观察 → 描写 → 动作 → 发言」推进：先看摄像头画面和麦克风信号，写现场描写，再给设备动作，最后发言。回复采用严格 JSON，程序拆出台词和设备指令，动作经安全层校验后才执行。

摄像头和麦克风各自形成反馈：画面变黑或没人时，角色会逐渐变得不耐烦，再升级到愤怒、暴怒；呻吟声分级，普通呻吟会小幅加码，惨叫会立即降低；长时间没有声音时，角色会主动挑逗。

### 设备控制与网页控制台

- 设备侧 A／B 双通道独立控制，内置 24 个波形（面板分类名「经典波形」）。
- 网页控制台负责聊天、手动控制、通道开关、通道强度上限（1～200，默认 100）和主题切换。
- 安全层负责强度上限、步长限制和过热保护；长按空格可急停。
- 摄像头／麦克风支持独立开关，并带失败警示与自动重试。
- 支持清空对话历史、更新检测（顶栏徽章提示新版本，可在设置中关闭）、公告浮窗和 DLC 导入（`.zip` 或 `.md`，导入即生效）。

## 🗺️ 计划

**短期**

- 架构改进：动作与台词分离（tool call 优先，不支持时回退 JSON），降低解析／兜底成本。
- Web UI 响应式优化 + 配置项 UI 补全。

**长期**

- 角色体系扩展：更多角色（各自含风格子项）以 DLC 方式接入，目录规范为 `content/pack/DLC<序号>-<角色>-<风格>`。
- ASR 可选开关（语音指令提取，默认关）。
- 郊狼 2.0（脉冲主机 V2／D-LAB ESTIM01）适配评估。
- 英文版（EN）待市场调研。

## ⚠️ 免责声明

本项目仅供**成年用户**在**自愿、知情、同意**的前提下使用，仅用于个人娱乐。请：

- 遵守所在地区法律法规；
- 评估自身身体状况，心脏病、心脏起搏器等健康风险人群请勿使用；
- 控制强度与时长，随时可用急停（长按空格 1 秒）中断；
- 使用本项目造成的任何后果由使用者自行承担，作者不承担任何责任。

## 📜 许可证

- 本仓库主体为作者原创的**专有软件**（All Rights Reserved，见 [LICENSE](LICENSE)）。
- `relay/` 目录源自 [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)（GPL-3.0），作为独立第三方组件随包分发，保留其原始许可证（`relay/LICENSE`）。
- **本体与 DLC**：多角色体系——每个角色自带若干风格档（轻／中／重）。「触手」角色随本体发布（纯爱版=轻，`content/pure/`）；其「调教版」（中）作为 DLC1、「品评会」角色（调教·中）作为 DLC2，存放在 [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) 仓库（成人内容，18+）。未来新角色照同一 DLC 机制接入。具体清单见下节「项目内容」。

## 🧩 项目内容

### 触手 · 纯爱版（本体，轻）

`content/pure/` 中是默认启用的「纯爱版」角色内容：

| 文件 | 说明 |
|---|---|
| `触手-角色提示词-纯爱.md` | 运行时提示词：风格、格式规则、轻量语料 |
| `触手-语料库-纯爱.md` | 纯爱向描写语料 |
| `触手-漫画设定-纯爱.md` | 角色与世界观设定 |

### DLC1：触手 · 调教版（中）

存放于 [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) 仓库（18+）。**推荐在程序内导入**：窗口左侧「角色设置」→「导入 DLC」→选择下载好的 `Coyote-in-Cradle-DLC1.zip`（或单个 `.md`），自动拷贝进 `content/pack/` 并启用，无需重启。

| 文件 | 说明 |
|---|---|
| `触手-角色提示词-调教.md` | 调教版运行时提示词 |
| `触手-语料库-调教.md` | 调教向描写语料 |
| `触手-漫画设定-调教.md` | 角色与世界观设定 |

### DLC2：品评会 · 调教版（中）

存放于 [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) 仓库（18+）。导入方式同上（选择 `Coyote-in-Cradle-DLC2.zip` 或单个 `.md`）——导入后，「角色设置」里会出现「品评会」角色卡片，切过去即用。

| 文件 | 说明 |
|---|---|
| `品评会-角色提示词-调教.md` | 主评身份：公开审评、装置支配、围观施压 |
| `品评会-语料库-调教.md` | 羞辱／支配／装置向描写语料 |
| `品评会-漫画设定-调教.md` | 贵族品评会世界观设定 |

**手动方式**：把对应 DLC 目录放进 `content/pack/`，再在 `config/character.yaml` 的 `roles.<角色>.profiles` 中启用其 `prompt_file`（参考 `config/character.example.yaml`）。新角色照 `content/pack/DLC<序号>-<角色>-<风格>/` 建目录，文件名沿用「角色名-」前缀。没有装好的角色／风格档会显示「未装 DLC」，并被切换拦截。

## 🚀 快速开始

### 一键安装（推荐）

下载最新 Release 的 `Coyote-in-Cradle-setup-v*.exe`，双击安装。桌面图标「Coyote in Cradle」点开即用：一个应用窗口，关窗口即全部退出，无需命令行与浏览器。

不想安装可下载免装 zip，解压后双击 `Coyote-in-Cradle.exe`（或备用 `start.bat`）。

### 环境要求

- Python 3.10+（主程序）。
- [Bun](https://bun.sh)（中继服务）。
- Node.js 18+（前端构建）。
- 可选依赖（不装则对应功能自动禁用）：
  - 摄像头：`pip install opencv-python`
  - 麦克风：`pip install sounddevice numpy`（只测音量分级，不做语音转写）

### 1. 安装依赖

```bat
pip install -r requirements.txt
cd relay & bun install
cd ..\frontend & npm install & npm run build
```

> 主程序通过 FastAPI 直接托管 `frontend/dist`，所以**必须先构建一次前端**。

### 2. 配置

复制示例配置并填写：

```bat
copy config\config.example.yaml config\config.yaml
copy config\character.example.yaml config\character.yaml
```

- `config/config.yaml`：填写 `llm.api_key`（或环境变量 `DGLAB_LLM_API_KEY`）和模型地址；先 `dry_run: true` 联调，接真机时改为 `false`。
- 也可以启动后打开网页 **「设置 → AI 模型配置」**，直接填写 API Key／地址／模型名：点「测试连接」验证，点「保存并生效」即时生效（无需重启；首次保存自动生成 `config.yaml`）。
- `config/character.yaml`：角色设定（默认「纯爱版」；调教版见 DLC1）。
- `config/device_channels.yaml`：通道与配件映射、强度基准（首次运行自动生成）。

### 3. 启动

双击 `start.bat`（自动：起中继 → 起主程序 → 开浏览器），或手动：

```bat
cd relay & bun run v4-server.ts        REM 窗口 1：中继（端口 9998）
python -m backend.main                 REM 窗口 2：主程序（端口 8000）
```

浏览器打开 <http://127.0.0.1:8000>。

### 4. 配对郊狼（手机 + 局域网）

1. 手机连接到**与电脑同一个 Wi-Fi**；
2. 打开 DG-LAB 4.0 App，进入 Socket V4 控制入口，扫描 Web 页面右侧二维码（形如 `https://dungeon-lab.cn/s/?v=1&action=socket&url=ws://192.168.x.x:9998?tid=...`）；
3. App 内蓝牙连接郊狼主机，页面状态变为「已配对」；
4. 若扫不上，检查防火墙是否放行 9998 端口（管理员运行）：
   `netsh advfirewall firewall add rule name="dglab-relay" dir=in action=allow protocol=TCP localport=9998`

## 🎛️ 使用说明

- **聊天**：左侧与 AI 对话，AI 返回台词 + 设备动作，动作经安全层校验后执行。
- **手动控制**：右侧每通道支持持续强度（保持型）、增减强度、清除和波形（可选时长与通道，持续波形可循环）。
- **通道与配件**：A=贴片、B=肛塞（可在「配件配置」中修改），基准强度按配件设定（默认贴片 15／肛塞 5）。
- **自动运行**：聊天栏顶部「自动运行」开关（清空按钮旁）开启后，按间隔自动循环「观察 → 描写 → 动作 → 发言」；摄像头／麦克风跟随自动运行启停。
- **急停**：页面大红按钮，或页面不在输入框时**长按空格 1 秒**（松手取消，防误触）；急停 = 全通道清零 + 清波形 + 暂停 AI 循环，点「解除急停」恢复。
- **安全约定**：本程序不设安全词口令，靠急停和「AI 察觉连续痛苦表达自动收敛」兜底；实机使用前先 `dry_run` 联调并确认强度基准。

## ❓ 常见问题

- **开场／聊天报「API Key 无效」**：官方与中转站的密钥不通用——确认 Base URL 与密钥配套（官方填 `https://api.deepseek.com`）；先点设置页「测试连接」验证再配对。
- **报「服务器返回了网页」／测试连接通过但对话抽风**：Base URL 填成了网页地址（应填 API 地址），或中转站不支持 JSON 模式 → 设置页**关掉「JSON 模式」**（程序自动兜底解析；开着时收到 400 也会自动降级重试）。
- **麦克风显示「未运行／启动中」**：先开自动运行（传感器跟随它）；按钮变橙色时悬停看具体原因（常见：台式机没有麦克风、系统禁用了麦克风权限）；没有插麦克风属于正常现象。
- **台式机没有麦克风**：不插也能玩，画面观察仍工作；麦克风功能自动报错提示，不影响其他功能。
- **更新提示**：顶栏出现「新版本 vX.Y.Z」徽章即可点下载；设置页可关闭自动检查更新。

## 🛡️ 安全设计

任何来源命令的唯一出口是 `backend/safety.py`：

1. 每通道独立强度上限（配置，默认 100），AI／手动超不过；
2. 单条指令强度变化 ≤ 40（防跳变）；
3. 单次波形／临时强度到点自动归零；
4. 设备过热 → 该通道上限临时降到 20；
5. 中继／App 断开 → 自动清零；
6. 急停（按钮／长按空格）= 清零 + 清波形 + 暂停循环；
7. 使用注意：电极不可跨心脏／颈部以上；不同配件请分别调低对应通道上限。

## 🤖 AI 指令协议

模型每次回复严格 JSON：

```json
{
  "line": "角色台词（原样显示）",
  "actions": [
    {"op": "temp_strength", "channel": "A", "value": 60, "duration_s": 3},
    {"op": "add_strength", "channel": "B", "delta": 10},
    {"op": "pulse", "channel": "A", "pattern": "短促连击", "duration_s": 2},
    {"op": "clear", "channel": "B"},
    {"op": "stop"}
  ]
}
```

波形库在 `config/waveforms.yaml`：`presets` 是中文名到波形的映射（含默认／最长时长），`custom` 存放官方波形的 64 帧数据。

## 🗂️ 目录结构

```text
AI-for-Coyote\
├── backend\             Python 后端（FastAPI：main / config / safety / relay_client / device_ops
│                        waveforms / llm / game_loop / camera / audio / logging_utils）
├── frontend\            React 19 + TS + Vite + Tailwind v4 桌面控制台（dist\ 为构建产物，由后端托管）
├── relay\               dglab-websocket-server（Bun，v4 端口 9998）
├── desktop\             桌面壳（pywebview 应用窗口，双击即用；shell.py + app.ico）
├── packaging\           打包脚本（免装 zip 组装 + Inno Setup 安装器模板）
├── config\              config.example.yaml（示例配置）、waveforms.yaml（波形库）
├── content\pure\        仓库自带内容：纯爱版提示词／语料／设定（默认角色）
├── content\roles\       自由聊角色内容（触手/品评会各档位提示词、语料，随包内置）
├── content\pack\dungeon\  地牢主题包（00-地牢 大包 + 触手 / 品评会 / 淫纹 theme pack）
├── logs\                程序运行日志（app.log）
└── start.bat             一键启动
```

## 🧑‍💻 前端开发

- 日常使用：后端直接托管 `frontend\dist`（改完前端先 `npm run build`）。
- 开发模式：`frontend\` 下 `npm run dev`（Vite 代理 `/api` 与 `/ws` 到 8000，浏览器打开 5173）。

## 📚 依赖

- Python 3.10+：`pip install -r requirements.txt`
- Bun（运行中继）：`npm install -g bun`
- Node 18+（前端构建）
- 桌面壳（仅源码运行桌面应用时需要）：`pip install pywebview`（打包时由脚本自动安装）
- 手机端：DG-LAB 4.0 App（v4 协议）

[回到顶部](#top)

<a id="english"></a>

## English

> **In one sentence:** An AI role-playing system where the AI plays a character, observes through the camera, listens through the microphone, and controls a Coyote（DG-Lab）device in real time.

Current themes: **Tentacles**（Pure Love／Training）, and **Appraisal Event**（Training, DLC）. The displayed tiers are Pure Love／Training／Humiliation（= light／medium／heavy）. More characters are connected through the DLC mechanism.

## ⬇️ Download（Windows）

Download the latest release here:

👉 <https://github.com/indhg/AI-for-Coyote/releases/latest>

**This project is the author's original proprietary software（All Rights Reserved）. Redistribution, resale and republishing through any channel are not authorized—please get it only from official channels.** Welcome to support the author on Twitter: <https://x.com/cinnanirch>

## 📦 Related repositories

This is a **multi-platform application**. Alongside this PC repository, there are two companion repositories:

| Repository | Link | Description |
|---|---|---|
| 🧪 **DLC repository** | [indhg/AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) | 18+ expansion content（currently DLC1-Tentacles-Training and DLC2-Appraisal Event-Training） |
| 📱 **Android client** | [indhg/Coyote-in-Cradle-Android](https://github.com/indhg/Coyote-in-Cradle-Android) | No computer required; connects directly to Coyote 3.0 over Bluetooth（BLE direct connection, no relay） |

It depends on the **Socket interface of Coyote + dglab-websocket-server**.

```text
Desktop app（or browser page） ⇄ Python app（FastAPI） ⇄ dglab-websocket-server v4（Bun） ⇄ DG-LAB 4.0 App（phone） ⇄ Coyote device（A／B channels）
                         │
                         └─ OpenAI-compatible model（character lines + structured device commands + camera／microphone observation）
```

## ✨ Features

### AI observation and role progression

Each AI round follows “observe → describe → act → speak”: it first reads the camera image and microphone signal, writes a scene description, produces device actions, and then speaks. The response is strict JSON; the program separates dialogue from device commands, and the safety layer validates actions before execution.

The camera and microphone provide separate feedback. When the image is dark or nobody is present, the character gradually becomes impatient, then angry and enraged. Vocal reactions are graded: ordinary moans slightly increase intensity, while screams immediately lower it. After a long period of silence, the character actively teases.

### Device control and web console

- Independent A／B channel control, with 24 built-in waveforms（the panel category is “Classic Waveforms”）.
- Web console for chat, manual control, channel toggles, per-channel intensity caps（1–200, default 100）, and theme switching.
- Safety layer for intensity caps, step limits, and overheating protection; hold Space to emergency-stop.
- Independent camera／microphone switches with failure warnings and automatic retry.
- Clear chat history, update checks（new-version badge in the top bar; can be disabled in Settings）, announcement pop-up, and DLC import（`.zip` or `.md`, effective immediately）.

## 🗺️ Roadmap

**Short term**

- Architecture improvement: separate actions from dialogue（tool calls first, JSON fallback when unsupported）to reduce parsing and fallback cost.
- Responsive Web UI improvements + a more complete configuration UI.

**Long term**

- Expand the character system: add more characters（each with style tiers）through DLC, using `content/pack/DLC<index>-<character>-<style>`.
- Optional ASR switch（voice-command extraction, off by default）.
- Evaluate Coyote 2.0（Pulse Host V2／D-LAB ESTIM01）support.
- English version（EN）pending market research.

## ⚠️ Disclaimer

This project is for **adults** only, and only for personal entertainment under **voluntary, informed, and consensual** conditions. Please:

- Follow the laws and regulations in your region.
- Assess your physical condition. People with heart disease, pacemakers, or similar health risks must not use it.
- Control intensity and duration; use the emergency stop at any time（hold Space for 1 second）.
- Users bear all consequences resulting from use of this project; the author assumes no responsibility.

## 📜 License

- The repository as a whole is the author's original **proprietary software**（All Rights Reserved, see [LICENSE](LICENSE)）.
- The `relay/` directory originates from [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)（GPL-3.0）and is shipped as an independent third-party component, retaining its original license（`relay/LICENSE`）.
- **Core content and DLC**: the multi-character system gives each character several style tiers（light／medium／heavy）. The “Tentacles” character ships with the core（Pure Love = light, `content/pure/`）; its Training version（medium）is DLC1, and the “Appraisal Event” character（Training · medium）is DLC2 in the [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) repository（adult content, 18+）. Future characters follow the same DLC mechanism. See “Project content” below for the detailed list.

## 🧩 Project content

### Tentacles · Pure Love（core, light）

`content/pure/` contains the default “Pure Love” character content:

| File | Description |
|---|---|
| `触手-角色提示词-纯爱.md` | Runtime prompt: style, format rules, and light corpus |
| `触手-语料库-纯爱.md` | Pure-Love descriptive corpus |
| `触手-漫画设定-纯爱.md` | Character and world setting |

### DLC1: Tentacles · Training（medium）

Stored in the [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) repository（18+）. **Importing from inside the program is recommended**: in the left-side “Character Settings” panel, choose “Import DLC”, select `Coyote-in-Cradle-DLC1.zip`（or a single `.md` file）, and it will be copied into `content/pack/` and enabled without a restart.

| File | Description |
|---|---|
| `触手-角色提示词-调教.md` | Training-version runtime prompt |
| `触手-语料库-调教.md` | Training-oriented descriptive corpus |
| `触手-漫画设定-调教.md` | Character and world setting |

### DLC2: Appraisal Event · Training（medium）

Stored in the [AI-for-Coyote-DLC](https://github.com/indhg/AI-for-Coyote-DLC) repository（18+, extreme content）. Import it the same way（select `Coyote-in-Cradle-DLC2.zip` or a single `.md` file）; after import, an “Appraisal Event” character card appears in “Character Settings” and is ready to use.

| File | Description |
|---|---|
| `品评会-角色提示词-调教.md` | Judge identity: public appraisal, device domination, and crowd pressure |
| `品评会-语料库-调教.md` | Humiliation／domination／device-oriented descriptive corpus |
| `品评会-漫画设定-调教.md` | Aristocratic appraisal-event world setting |

**Manual method**: place the corresponding DLC directory in `content/pack/`, then enable its `prompt_file` under `roles.<character>.profiles` in `config/character.yaml`（see `config/character.example.yaml`）. Create new characters under `content/pack/DLC<index>-<character>-<style>/`, keeping the “character name-” filename prefix. An uninstalled character or style tier is shown as “DLC not installed” and cannot be selected.

## 🚀 Quick start

### One-click installation（recommended）

Download the latest Release `Coyote-in-Cradle-setup-v*.exe` and double-click to install. Open the “Coyote in Cradle” desktop shortcut to start: everything runs in one application window, and closing it exits all components; no command line or browser is required.

Prefer a portable version? Download the no-install zip, extract it, and double-click `Coyote-in-Cradle.exe`（or the fallback `start.bat`）.

### Requirements

- Python 3.10+（main program）
- [Bun](https://bun.sh)（relay service）
- Node.js 18+（frontend build）
- Optional dependencies（the corresponding feature is disabled automatically when absent）:
  - Camera: `pip install opencv-python`
  - Microphone: `pip install sounddevice numpy`（volume grading only; no speech transcription）

### 1. Install dependencies

```bat
pip install -r requirements.txt
cd relay & bun install
cd ..\frontend & npm install & npm run build
```

> The main program serves `frontend/dist` directly through FastAPI, so you **must build the frontend once first**.

### 2. Configure

Copy the example configuration files and fill them in:

```bat
copy config\config.example.yaml config\config.yaml
copy config\character.example.yaml config\character.yaml
```

- `config/config.yaml`: set `llm.api_key`（or the `DGLAB_LLM_API_KEY` environment variable）and the model address; use `dry_run: true` for integration testing, then change it to `false` for a real device.
- You can also open **“Settings → AI Model Configuration”** after startup and enter the API Key, address, and model name directly. “Test Connection” verifies it; “Save and Apply” takes effect immediately（no restart; the first save creates `config.yaml` automatically）.
- `config/character.yaml`: character settings（default: “Pure Love”; see DLC1 for Training）
- `config/device_channels.yaml`: channel and accessory mapping plus intensity baselines（generated automatically on first run）

### 3. Start

Double-click `start.bat`（starts the relay, starts the main program, and opens the browser automatically）, or run manually:

```bat
cd relay & bun run v4-server.ts        REM Window 1: relay（port 9998）
python -m backend.main                 REM Window 2: main program（port 8000）
```

Open <http://127.0.0.1:8000> in a browser.

### 4. Pair the Coyote（phone + LAN）

1. Connect the phone to the **same Wi-Fi network as the computer**.
2. Open the DG-LAB 4.0 App, enter the Socket V4 control entry, and scan the QR code on the right side of the web page（for example, `https://dungeon-lab.cn/s/?v=1&action=socket&url=ws://192.168.x.x:9998?tid=...`）.
3. Connect the Coyote device over Bluetooth inside the App; the page status changes to “Paired”.
4. If scanning fails, check that the firewall allows port 9998（run as administrator）:
   `netsh advfirewall firewall add rule name="dglab-relay" dir=in action=allow protocol=TCP localport=9998`

## 🎛️ Usage

- **Chat**: talk with the AI on the left; it returns dialogue and device actions, which are validated by the safety layer before execution.
- **Manual control**: on the right, each channel supports sustained intensity（hold mode）, intensity increase/decrease, clear, and waveform control（optional duration and channel; sustained waveforms can loop）.
- **Channels and accessories**: A = patch, B = anal plug（editable in “Accessory Configuration”）. Baselines follow the accessory（patch 15／anal plug 5 by default）.
- **Autopilot**: enable “Autopilot” at the top of the chat panel（beside the Clear button）to loop “observe → describe → act → speak” at an interval; the camera and microphone follow autopilot.
- **Emergency stop**: use the large red button, or **hold Space for 1 second** when the page is not focused on an input（release cancels to prevent accidental activation）. It clears every channel, clears waveforms, and pauses the AI loop; select “Release Emergency Stop” to resume.
- **Safety agreement**: there is no safety-word password. The fallback is the emergency stop plus automatic AI convergence after repeated expressions of pain. Run an integration test with `dry_run` and confirm intensity baselines before using a real device.

## ❓ FAQ

- **“Invalid API Key” at startup or in chat**: official and relay-provider keys are not interchangeable. Confirm that the Base URL and key belong together（for the official endpoint, use `https://api.deepseek.com`）; test it in Settings before pairing.
- **“The server returned a webpage”／connection test passes but chat behaves strangely**: the Base URL may be a web page instead of an API endpoint, or the relay provider may not support JSON mode. **Turn off “JSON Mode”** in Settings; the program falls back to parsing automatically and retries after a 400 response.
- **Microphone shows “Not running／Starting”**: enable autopilot first（sensors follow it）. Hover over the orange button for the reason（common causes are no desktop microphone or disabled system permission）. No microphone connected is normal.
- **No microphone on the desktop**: the program still works without one and camera observation continues; the microphone feature shows an automatic error notice without affecting other functions.
- **Update notice**: click the “New version vX.Y.Z” badge in the top bar to download; automatic update checks can be disabled in Settings.

## 🛡️ Safety design

The only exit for commands from any source is `backend/safety.py`:

1. Independent per-channel intensity caps（configured, default 100）that AI and manual control cannot exceed.
2. Intensity change per command ≤ 40（prevents jumps）.
3. Waveforms and temporary intensity return to zero automatically when their duration ends.
4. Overheating temporarily lowers the affected channel cap to 20.
5. Relay／App disconnection automatically clears intensity.
6. Emergency stop（button／hold Space）= clear intensity + clear waveforms + pause the loop.
7. Safety note: do not place electrodes across the heart or above the neck; lower the cap separately for different accessories.

## 🤖 AI command protocol

Every model response is strict JSON:

```json
{
  "line": "Character dialogue（displayed as-is）",
  "actions": [
    {"op": "temp_strength", "channel": "A", "value": 60, "duration_s": 3},
    {"op": "add_strength", "channel": "B", "delta": 10},
    {"op": "pulse", "channel": "A", "pattern": "短促连击", "duration_s": 2},
    {"op": "clear", "channel": "B"},
    {"op": "stop"}
  ]
}
```

The waveform library is in `config/waveforms.yaml`: `presets` maps Chinese names to waveforms（including default／maximum durations）, and `custom` stores the official waveform data as 64 frames.

## 🗂️ Directory structure

```text
AI-for-Coyote\
├── backend\             Python backend（FastAPI: main / config / safety / relay_client / device_ops
│                        waveforms / llm / game_loop / camera / audio / logging_utils）
├── frontend\            React 19 + TS + Vite + Tailwind v4 desktop console（dist\ is built and served by the backend）
├── relay\               dglab-websocket-server（Bun, v4 on port 9998）
├── desktop\             Desktop shell（pywebview app window; double-click to use; shell.py + app.ico）
├── packaging\           Packaging scripts（portable zip assembly + Inno Setup installer template）
├── config\              config.example.yaml（example configuration）, waveforms.yaml（waveform library）
├── content\pure\        Built-in content: Pure-Love prompts／corpus／setting（default character）
├── content\roles\       Free-chat role content（Tentacle / Appraisal tier prompts & corpus, bundled）
├── content\pack\dungeon\  Dungeon theme packs（00-地牢 master pack + Tentacle / Appraisal / 淫纹 theme packs）
├── logs\                Runtime logs（app.log）
└── start.bat             One-click startup
```

## 🧑‍💻 Frontend development

- Normal use: the backend serves `frontend\dist` directly（run `npm run build` after frontend changes）.
- Development mode: run `npm run dev` under `frontend\`（Vite proxies `/api` and `/ws` to port 8000; open port 5173 in the browser）.

## 📚 Dependencies

- Python 3.10+: `pip install -r requirements.txt`
- Bun（relay runtime）: `npm install -g bun`
- Node 18+（frontend build）
- Desktop shell（only needed to run the desktop app from source）: `pip install pywebview`（the packaging script installs it automatically when packaging）
- Phone client: DG-LAB 4.0 App（v4 protocol）

[Back to top](#top)
