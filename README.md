# AI for Coyote（AI for 郊狼）

「AI 扮演角色（触手）+ 摄像头/麦克风实时观察玩家反应 + 实时控制郊狼(DG-Lab)设备」的闭环程序。

参考示例（ESP32 闭环）换成了 **郊狼 + dglab-websocket-server 的 socket 接口**：

```
浏览器 Web 页面 ⇄ Python 主程序(FastAPI) ⇄ dglab-websocket-server v4(Bun) ⇄ DG-LAB 4.0 App(手机) ⇄ 郊狼主机(A/B 通道)
                     │
                     └─ OpenAI 兼容模型（角色台词 + 结构化设备指令 + 摄像头/麦克风观察）
```

## 功能

AI 每轮按「观察 → 描写 → 动作 → 发言」推进：先看摄像头画面和麦克风信号，写现场描写，再给设备动作，最后发言。回复是严格 JSON，程序拆出台词和设备指令，动作经安全层校验后才执行。

摄像头和麦克风各自形成反馈。画面变黑或没人，角色会不耐烦，再升级到愤怒、暴怒。呻吟声分级：普通呻吟小幅加码，惨叫立即降低；长时间没声音，角色主动挑逗。

设备侧 A/B 双通道独立控制，内置 24 个波形（面板分类名「经典波形」）。网页控制台负责聊天、手动控制、通道开关、强度修正（50%~150%）和风格切换；安全层管强度上限、步长限制、过热保护，空格键急停。

## ⚠️ 免责声明

本项目仅供**成年用户**在**自愿、知情、同意**的前提下使用，仅用于个人娱乐。请：

- 遵守所在地区法律法规；
- 评估自身身体状况，心脏病、心脏起搏器等健康风险人群请勿使用；
- 控制强度与时长，随时可用急停（空格键）中断；
- 使用本项目造成的任何后果由使用者自行承担，作者不承担任何责任。

## 许可证

- 本仓库整体以 **GPL-3.0** 发布（见 [LICENSE](LICENSE)）。
- `relay/` 目录源自 [dglab-websocket-server](https://github.com/ws94666ws/dglab-websocket-server)（GPL-3.0），保留其原始许可证。
- **本体与 DLC**：仓库本体自带轻口味的「纯爱版」角色（`content/pure/`）。「调教版」提示词与 NSFW 语料作为 DLC1，未来还可能增加更多 DLC；这类内容较为露骨，暂不公开提供，分发方式待定。具体清单见下节「项目内容」。

## 项目内容

### 本体

`content/pure/` 里是默认启用的「纯爱版」角色内容：

| 文件 | 说明 |
|---|---|
| `触手-角色提示词-纯爱.md` | 运行时提示词：风格、格式规则、轻量语料 |
| `触手-语料库-纯爱.md` | 纯爱向描写语料 |
| `触手-漫画设定-纯爱.md` | 角色与世界观设定 |

### DLC1：调教版

`content/pack/DLC1-调教版/`（gitignore）：

| 文件 | 说明 |
|---|---|
| `触手-角色提示词-调教.md` | 调教版运行时提示词 |
| `触手-语料库-调教.md` | 调教向描写语料 |
| `触手-漫画设定-调教.md` | 角色与世界观设定 |

新 DLC 照 `content/pack/DLC<序号>-<名称>/` 建目录，文件名沿用「角色名-」前缀；在 `config/character.yaml` 里加对应 profile 并指向其提示词文件，重启后侧边栏即可切换。没装好的 DLC 会显示「未装DLC」并被切换拦截。

## 快速开始

### 环境要求

- Python 3.10+（主程序）
- [Bun](https://bun.sh)（中继服务）
- Node.js 18+（前端构建）
- 可选依赖（不装则对应功能自动禁用）：
  - 摄像头：`pip install opencv-python`
  - 麦克风：`pip install faster-whisper sounddevice`（首次运行会下载 whisper 模型）

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

- `config/config.yaml`：填 `llm.api_key`（或环境变量 `DGLAB_LLM_API_KEY`）、模型地址；先 `dry_run: true` 联调，接真机时改 `false`
- 也可以启动后打开网页 **「设置 → AI 模型配置」** 直接填写 API Key / 地址 / 模型名：点「测试连接」验证、点「保存并生效」即时生效（无需重启；首次保存自动生成 config.yaml）
- `config/character.yaml`：角色设定（默认「纯爱版」；调教版见 DLC1）
- `config/device_channels.yaml`：通道与配件映射、强度基准（首次运行自动生成）

### 3. 启动

双击 `start.bat`（自动：起中继 → 起主程序 → 开浏览器），或手动：

```bat
cd relay & bun run v4-server.ts        REM 窗口 1：中继（端口 9998）
python -m backend.main                 REM 窗口 2：主程序（端口 8000）
```

浏览器打开 http://127.0.0.1:8000 。

### 4. 配对郊狼（手机 + 局域网）

1. 手机连到**与电脑同一个 Wi-Fi**；
2. 打开 DG-LAB 4.0 App，进入 Socket V4 控制入口，扫描 Web 页面右侧二维码
   （形如 `https://dungeon-lab.cn/s/?v=1&action=socket&url=ws://192.168.x.x:9998?tid=...`）；
3. App 内蓝牙连接郊狼主机，页面状态变为「已配对」；
4. 若扫不上，检查防火墙是否放行 9998 端口（管理员运行）：
   `netsh advfirewall firewall add rule name="dglab-relay" dir=in action=allow protocol=TCP localport=9998`

## 使用说明

- **聊天**：左侧与 AI 对话，AI 返回台词 + 设备动作，动作经安全层校验后执行
- **手动控制**：右侧每通道持续强度（保持型）/ 增减强度 / 清除 / 波形（可选时长与通道，持续波形可循环）
- **通道与配件**：A=贴片、B=肛塞（可在「配件配置」中修改），基准强度按配件设定（默认贴片 15 / 肛塞 5）；「强度修正」滑块（50%~150%）只乘 AI 发出的强度，不影响手动控制
- **自动运行**：顶部开关开启后按间隔自动循环「观察 → 描写 → 动作 → 发言」
- **急停**：页面大红按钮，或页面不在输入框时按**空格**；急停 = 全通道清零 + 清波形 + 暂停 AI 循环，点「解除急停」恢复
- **安全约定**：本程序不设安全词口令，靠急停和「AI 察觉连续痛苦表达自动收敛」兜底；实机使用前先 `dry_run` 联调并确认强度基准

## 安全设计（任何来源命令的唯一出口是 `backend/safety.py`）

1. 每通道独立强度上限（配置，默认 100），AI/手动超不过；
2. 单条指令强度变化 ≤ 40（防跳变）；
3. 单次波形/临时强度到点自动归零；
4. 设备过热 → 该通道上限临时降到 20；
5. 中继/App 断开 → 自动清零；
6. 急停（按钮/空格）= 清零 + 清波形 + 暂停循环；
7. 使用注意：电极不可跨心脏/颈部以上；不同配件请分别调低对应通道上限。

## AI 指令协议

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

波形库在 `config/waveforms.yaml`：`presets` 是中文名到波形的映射（含默认/最长时长），`custom` 存放官方波形的 64 帧数据。

## 目录结构

```
AI-for-Coyote\
├── backend\             Python 后端（FastAPI：main / config / safety / relay_client / device_ops
│                        waveforms / llm / game_loop / camera / audio / logging_utils）
├── frontend\            React 19 + TS + Vite 桌面控制台（dist\ 为构建产物，由后端托管）
├── relay\               dglab-websocket-server（Bun，v4 端口 9998）
├── config\              config.example.yaml（示例配置）、waveforms.yaml（波形库）
├── content\pure\        仓库自带内容：纯爱版提示词/语料/设定（默认角色）
├── content\pack\        DLC 系列（DLC1-调教版等，gitignore）
├── logs\                程序运行日志（app.log）
└── start.bat            一键启动
```

## 前端开发

- 日常使用：后端直接托管 `frontend\dist`（改完前端先 `npm run build`）
- 开发模式：`frontend\` 下 `npm run dev`（Vite 代理 /api 与 /ws 到 8000，浏览器开 5173）

## 依赖

- Python 3.10+：`pip install -r requirements.txt`
- Bun（运行中继）：`npm install -g bun`
- Node 18+（前端构建）
- 手机端：DG-LAB 4.0 App（v4 协议）
