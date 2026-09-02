/**
 * UI 语言层（EN 版 UI 落地，按 T051-英文版-Grok 术语表/英译表实施）。
 *
 * 用法：
 *   const t = useT();            // 组件内；语言随 state.lang 自动重渲染
 *   <span>{t("自动运行")}</span>
 *   带变量：t("强度 {level}", { level })
 *
 * 约定：
 * - 中文为代码里的唯一原文（默认语言），EN 查 DICT；查不到原样回中文（不阻断）。
 * - 组件扫掠时把「整条可见文案」作为 key（含 {var} 占位），不要拆字面量。
 * - 变量名仅用于词序占位；DICT 中中文与英文各自保留自己的语序占位。
 * - UI 层允许 Channel/A/B 等词；角色台词禁令不适用于 UI（T051 §1.4/§6）。
 */
import { useApp } from "./store";

export type UiLang = "zh" | "en";

export function useUiLang(): UiLang {
  return (useApp((st) => st.state?.lang as UiLang | undefined) ?? "zh");
}

/** 非 React 语境读当前语言（定时器/回调内用；组件内请用 useUiLang/useT 保证重渲染）。 */
export function uiLang(): UiLang {
  const lang = useApp.getState().state?.lang as UiLang | undefined;
  return lang ?? "zh";
}

type Vars = Record<string, string | number>;

/** 中文 → 英文 词典（UI 全量）。种子 = T051 术语表；组件扫掠时逐条并入。 */
const DICT: Record<string, string> = {
  // ---------- 术语表种子（T051 §1） ----------
  // 产品与导航
  控制台: "Console",
  设置: "Settings",
  帮助: "Help",
  公告: "Notice",
  新手引导: "Tour",
  添加配对设备: "Add / pair device",
  当前入口: "Theme",
  主题: "Theme",
  风格: "Style",
  昵称: "Name",
  "称谓（AI 怎么叫你）": "Name (what the AI calls you)",
  小柳: "Liu",
  配件设置: "Accessories",
  自选组合: "Waves",
  设备状态: "Device",
  设备: "Device",
  作者主页: "Author",
  // 档位显示名（内部键不变，仅显示）
  轻: "Tender",
  中: "Dominant",
  重: "Rough",
  纯爱: "Tender",
  调教: "Dominant",
  凌辱: "Rough",
  正式: "Rough",
  体验版: "Trial",
  强度: "Intensity",
  // 设备 / 安全 / 运行
  配对: "Pair",
  扫码配对: "Pair",
  二维码: "QR code",
  中继: "Relay",
  急停: "E-Stop",
  解除急停: "Clear E-Stop",
  全部清零: "Zero all",
  自动运行: "Autopilot",
  测试模式: "Test mode",
  模拟设备: "Simulator",
  通道: "Channel",
  "A 通道": "Channel A",
  "B 通道": "Channel B",
  // 角色名
  触手: "Tentacle",
  品评会: "Appraisal",
  哥布林: "Goblin",
  史莱姆: "Slime",
  蛛后: "Arachne",
  魅魔: "Succubus",
  淫纹: "Sigil",
  地牢刻印: "Marks",
  基础: "Base",
  紫金地牢: "Violet Dungeon",
  主人: "Master",
  // 常见动作/状态短词（组件级补充会继续并入）
  开始: "Start",
  停止: "Stop",
  保存: "Save",
  取消: "Cancel",
  清除: "Clear",
  清空: "Clear",
  重试: "Retry",
  关闭: "Off",
  打开: "On",
  // ---------- 试点批次（TopBar/App/Sidebar/BottomBar/ChatPanel 头） ----------
  "郊狼 · AI 驯服师": "Coyote · AI Tamer",
  作者水印: "Author mark",
  "Coyote in Cradle · 作者原创": "Coyote in Cradle · original work",
  进入地牢: "Enter dungeon",
  "新版本 {latest}，点击前往下载": "{latest} is out — download",
  "亟待更新…": "Update ready…",
  "设备 / 视图": "Device / views",
  "角色 / 入口": "Theme / nav",
  "收起 ✕": "Close ✕",
  收起设备面板: "Hide device panel",
  打开设备面板: "Show device panel",
  收起角色面板: "Hide theme panel",
  打开角色面板: "Show theme panel",
  "「急停中…」": "E-Stop…",
  松开取消: "Release to cancel",
  "郊狼 3.0": "Coyote 3.0",
  "电量 {n}%": "Battery {n}%",
  "A口状态 {n}": "Port A {n}",
  "B口状态 {n}": "Port B {n}",
  已连接: "Connected",
  等待配对: "Waiting to pair",
  未连接: "Disconnected",
  "添加 / 配对设备": "Add / pair device",
  "急停（长按空格）": "E-Stop (hold Space)",
  "强度与波形均受安全上限钳制；": "Intensity and waves are capped.",
  "急停（长按空格 / 底部按钮）可随时清零。": "E-Stop (hold Space / bottom button) zeros output any time.",
  在大厅配置主题后进入: "Set themes in the lobby, then enter",
  本局信息: "This run",
  "意志 {bars}": "Will {bars}",
  亲和: "Affinity",
  "第 {f} 层 · 第 {r} 房 · 回合 {t}": "Floor {f} · Room {r} · Turn {t}",
  "恢复（解除急停）": "Resume (clear E-Stop)",
  "暂停（急停：全部清零并暂停 AI）": "Pause (E-Stop: zero output and pause AI)",
  "空格 = 急停": "Space = E-Stop",
  "—— 已切换至 {x} ——": "—— Theme: {x} ——",
  "当前电击强度档（轻/中/重 = ×0.7/×1.0/×1.3，与对话无关）":
    "Intensity tier (Tender / Dominant / Rough = ×0.7/×1.0/×1.3; not dialogue)",
  "强度 {v}": "Intensity {v}",
  "AI 内容语言（提示词/台词/语料）：中文 / English": "AI content language (prompts / lines / corpus): 中文 / English",
  "当前角色暂无英文版（英文稿未随内容提供）": "No English sheet for this theme yet",
  停止自动运行: "Stop Autopilot",
  "开始自动运行（AI 自主回合，摄像头/麦克风跟随启停）": "Start Autopilot (AI takes turns; camera / mic follow)",
  "退出测试模式，恢复扫码配对": "Exit test mode, go back to QR pairing",
  "测试 ✕": "Test ✕",
  "清空对话历史？将清空聊天记录与 AI 的记忆上下文，设备强度不受影响。":
    "Clear the chat? This wipes the transcript and the AI's memory. Intensity stays.",
  "—— 对话历史已清空 ——": "—— Chat cleared ——",
  "⛔ 已急停：设备已清零、AI 已暂停——到底部按「解除」恢复":
    "⛔ E-Stop: output zeroed, AI paused — Clear E-Stop on the bottom bar",
  // ---------- 批次2（ChatPanel 配对区 + RoleCard + commands） ----------
  二维码加载失败: "Couldn't load the QR",
  "等待中继就绪，正在生成二维码…": "Waiting on the relay… making a QR",
  "自动重试已暂停，请确认中继服务后点击重试": "Auto-retry paused — check the relay and tap Retry",
  "会自动重试，或点下方手动重试": "Retrying, or tap Retry below",
  "二维码会自动重试，稍候即可": "QR will retry on its own",
  配对二维码: "Pairing QR",
  "手机打开 DG-LAB 4.0 App 扫码配对": "Open DG-LAB 4.0 on your phone and scan",
  "⚠️ 配对后请在 App 里打开「输出」开关（解除屏蔽），否则设备不会有感觉":
    "⚠️ After pairing, turn Output on in the App or you won't feel anything",
  "没有郊狼？": "No Coyote?",
  "不连接设备，用模拟设备试跑聊天 / 地牢 / AI 全流程（不会真正电击）":
    "Skip the device. Run chat / dungeon / AI on the simulator (no shock)",
  "点击进入测试（模拟设备）": "Enter test (simulator)",
  "⚠️ 所有通道都已关闭，AI 不会输出任何刺激——请在左侧通道卡打开至少一个通道":
    "⚠️ Every channel is off. The AI won't output — turn on at least one channel card",
  "✓ 已执行 {n}": "✓ sent {n}",
  "✖ 未发送 {n}": "✖ blocked {n}",
  "切换角色入口与电击强度": "Switch theme & intensity",
  推荐: "Pick",
  新手推荐: "Start here",
  "强度 · {v}": "Intensity · {v}",
  角色入口: "Themes",
  展开入口列表: "Show themes",
  "（点击换入口）": "(click to change)",
  "当前 ×{s}": "now ×{s}",
  "切换失败：{msg}": "Couldn't switch: {msg}",
  "强度档切换失败：{msg}": "Couldn't switch intensity: {msg}",
  "✖ 请求失败：{e}": "✖ request failed: {e}",
  "⚠ 急停：全部清零、波形停止、AI 循环暂停": "⚠ E-Stop: zeroed, waves stopped, AI paused",
  急停已解除: "E-Stop cleared",
  // ---------- 配件（§2.10）与波形盘（§2.14/§1.6） ----------
  贴片: "Pads",
  肛塞: "Plug",
  待适配: "Unset",
  更换配件: "Change accessory",
  "位置（如 大腿根内侧）": "Location (e.g. inner thigh)",
  "改动称谓的时候记得敲回车（Enter）": "Press Enter after you edit a field",
  "未工作的通道不会被描写。": "Off channels stay out of the writing.",
  "急停中：所有设备动作被拒绝。点「解除急停」恢复（焦点不在输入框时长按空格 1 秒触发急停）。":
    "E-Stop is on. Device commands are blocked. Hit Clear E-Stop (or hold Space 1s when you're not in a text field).",
  "该分类暂无波形（可在 config\\waveforms.yaml 自定义）": "No waves in this category (edit config\\waveforms.yaml)",
  经典波形: "Classic",
  挤压: "Squeeze",
  气泡: "Bubble",
  律动: "Rhythm",
  电波: "Airwave",
  舞步: "Dance",
  攀登: "Climb",
  树荫: "Shade",
  脉冲: "Pulse",
  呼吸: "Breath",
  潮汐: "Tide",
  连击: "Combo",
  快速按捏: "Rapid Pinch",
  按捏渐强: "Rising Pinch",
  心跳节奏: "Heartbeat",
  压缩: "Compress",
  节奏步伐: "Cadence",
  颗粒摩擦: "Grain",
  渐变弹跳: "Bounce",
  波浪涟漪: "Ripple",
  雨水冲刷: "Rain",
  变速敲击: "Knock",
  信号灯: "Signal",
  挑逗1: "Tease 1",
  挑逗2: "Tease 2",
  // ---------- 通道卡（§2.12）/ 设备状态（§2.13） ----------
  "A / B 双通道": "A / B channels",
  "A/B 联动": "Link A/B",
  "{ch} 通道": "Channel {ch}",
  "关闭 {ch} 通道": "Turn off channel {ch}",
  "开启 {ch} 通道": "Turn on channel {ch}",
  开: "On",
  关: "Off",
  调整该通道强度上限: "Channel intensity cap",
  上限可调: "cap",
  "设定{req}": "want {req}",
  "强度上限（1~{hardCap}）": "Cap (1–{hardCap})",
  已关闭: "Closed",
  播放中: "Playing",
  工作中: "Active",
  未工作: "Off",
  "{ch} 减弱": "{ch} down",
  "{ch} 增强": "{ch} up",
  播放: "Play",
  "点击关闭{label}": "Turn off {label}",
  "点击开启{label}": "Turn on {label}",
  "自动运行未开启，{label}不会启动——请打开聊天栏顶部「清空」旁边的「自动运行」开关":
    "Autopilot is off, so {label} won't start — turn on Autopilot next to Clear in the chat bar",
  "{label}启动中…": "{label} starting…",
  错误: "Error",
  摄像头: "Camera",
  麦克风: "Mic",
  "自动运行未开启，麦克风未启动": "Autopilot is off, mic is idle",
  "监听中…": "Listening…",
  未运行: "Idle",
  "启动中…": "Starting…",
  未开启: "Off",
  波形: "Wave",
  // ---------- 批次3（公告/帮助设置/引导/地牢外壳） ----------
  "本软件完全免费": "This software is free.",
  "⚠ 任何以本软件名义要求付费的版本均为盗版": "⚠ Anyone charging for it is a pirate",
  "未经授权，禁止转载、倒卖、二次分发或制作衍生发布包。":
    "No republishing, resale, redistribution, or derivative release packs without permission.",
  "拓展包及其他 NSFW 内容属于独立的 18+ 内容范围，与主仓库分开维护。地牢内容目前仍在开发中，暂不作为公开发布内容。":
    "DLC and other NSFW content is separate 18+ material, kept outside the main repo. The dungeon is still in development and not part of the public release.",
  "欢迎通过作者主页获取更新信息或支持作者：": "Updates and support:",
  知道了: "Got it",
  "App 配对（同一 Wi-Fi，DG-LAB 4.0 扫码）": "Pair the App (same Wi-Fi, DG-LAB 4.0)",
  "重试（4 秒后自动）": "Retry (auto in 4s)",
  中继服务仍未就绪: "Relay isn't ready yet",
  "请确认服务后点击重试": "Check the service and tap Retry",
  二维码会低频自动重试: "QR retries on its own",
  "已在线 {n} 台；新设备请重扫上方二维码": "{n} online — rescan for a new device",
  "用 DG-LAB 4.0 App 扫上方二维码配对（同一 Wi-Fi）": "Scan with DG-LAB 4.0 to pair (same Wi-Fi)",
  "\n当前电脑 IP: {ip}": "\nThis PC IP: {ip}",
  "\n其他 IP: {list}": "\nOther IPs: {list}",
  "AI 自动运行间隔": "AI autopilot interval",
  "秒/轮": "s / turn",
  "保存中…": "Saving…",
  已生效: "Applied",
  "保存失败，请重试": "Save failed, try again",
  "修改 config\\character.yaml（主题/示例）保存后下一条消息即生效；":
    "Edit config\\character.yaml (theme / examples); the next message picks it up.",
  "AI 模型配置在下方填写、保存即生效；其余 config.yaml / config\\waveforms.yaml 修改后需重启程序。":
    "AI model settings below apply on save. Other edits to config.yaml / config\\waveforms.yaml need a restart.",
  "作者主页: x.com/cinnanirch": "Author: x.com/cinnanirch",
  "亟待更新：{latest}，点击下载 →": "Update ready: {latest} — download →",
  已是最新版本: "You're on the latest",
  "更多帮助内容（进阶指引、FAQ）即将上线。": "More help (advanced / FAQ) coming soon.",
  "已保存并生效（模型：{model}）": "Saved ({model})",
  "保存失败：{e}": "Save failed: {e}",
  "已保存到 config.yaml，此处修改保存即生效、无需重启。":
    "Saved in config.yaml. Edits here apply on save, no restart.",
  "尚未保存过（当前用示例配置），首次保存后写入 config.yaml。":
    "Not saved yet (sample config). First save writes config.yaml.",
  " 已有密钥：{masked}": "Key on file: {masked}",
  " 当前无密钥。": "No key yet.",
  "已保存 {masked}；粘贴新密钥覆盖，留空保存 = 清除":
    "Saved {masked}; paste a new key to replace, save empty to clear",
  "粘贴 API Key（留空则使用环境变量 DGLAB_LLM_API_KEY）": "Paste API key (empty = env DGLAB_LLM_API_KEY)",
  模型名: "Model",
  "JSON 模式（部分中转站不兼容，可关闭）": "JSON mode (some proxies hate this — uncheck)",
  测试连接: "Test connection",
  保存并生效: "Save",
  自动检查更新: "Check for updates",
  "发现新版本 {latest}，点击下载 →": "{latest} is out — download →",
  "已是最新（{latest}）": "Latest ({latest})",
  尚未检查到更新: "No update check yet",
  "更新检查已关闭（版本锁定）": "Update check off (version locked)",
  "第一步：配置 AI": "Step 1: Set up the AI",
  "点右上角「设置」，先完成 AI 模型配置。": "Tap Settings up top, then fill in the AI model config.",
  "粘贴 API Key": "Paste your API key",
  "填服务商给你的真实密钥（官方 DeepSeek 开放平台可创建）。":
    "Paste the real key from your provider (DeepSeek's open platform lets you create one).",
  "填 API 接口地址": "Enter the API base URL",
  "填 API 接口地址，不是网页首页。\n官方示例：https://api.deepseek.com":
    "This is the API endpoint, not the website.\nExample: https://api.deepseek.com",
  填模型名: "Enter the model name",
  "地址、密钥、模型名要属于同一服务。\n官方示例：**deepseek-v4-flash-vision-exp**":
    "URL, key and model must come from the same service.\nExample: **deepseek-v4-flash-vision-exp**",
  先测试连接: "Test first",
  "点「测试连接」，通过后再保存。": "Hit Test connection — save only after it passes.",
  "保存即生效。": "Saving applies it right away.",
  配对郊狼: "Pair your Coyote",
  "手机连同一 Wi-Fi，用 DG-LAB 4.0 App 扫码；配对后在 App 里关闭「屏蔽输出」，否则设备不会有感觉。":
    "On the same Wi-Fi, scan with DG-LAB 4.0; after pairing, unblock Output in the app or you won't feel anything.",
  打开自动运行: "Turn on Autopilot",
  "AI 开始自动观察、发言、动设备；摄像头/麦克风跟随它启停。":
    "The AI watches, talks and works the device on its own; the camera and mic follow it.",
  记住急停: "Remember E-Stop",
  "长按空格 1 秒，或点这个按钮，全部停止。":
    "Hold Space for 1s, or hit this button — everything stops.",
  "需要更丰富的体验？点顶栏「帮助」，进阶指引即将上线喵~":
    "Want more? The Help tab up top will soon hold advanced guides.",
  跳过: "Skip",
  上一步: "Back",
  下一步: "Next",
  "一座变幻莫测的地下城…": "A dungeon that won't sit still…",
  "本局主题（至少选择 3 项）": "Themes this run (pick at least 3)",
  暂无已装主题包: "No theme packs installed",
  "地牢刻印、淫纹（基础包，必选）": "Marks, Sigil (base pack, required)",
  "{f} 层": "{f} floors",
  "深度（层数）": "Depth (floors)",
  "内容封顶（本局最高分级）": "Cap (highest style this run)",
  "地牢建设中 · 暂未开放": "Under construction · not open yet",
  "紫金地牢尚未完工，内容打磨完成后开放": "Violet Dungeon isn't ready — it opens after the content polish",
  "紫金地牢尚未完工，暂不能开始冒险": "Violet Dungeon isn't ready yet",
  "正在开启…": "Opening…",
  "再选 {n} 个主题（至少 {min} 个）": "Pick {n} more (need {min})",
  "进入前需确认 18+ 同意（可勾选不再提示）": "18+ consent first (you can hide this next time)",
  开始前确认: "Before you enter",
  "· 虚构内容，双方成人，可随时离开": "· Fiction. Adults. Leave whenever you want.",
  "· 空格长按 / 底栏急停会立即清零设备": "· Hold Space / bottom E-Stop zeros the device now",
  "· 体感受本机上限与通道开关约束": "· Feel is capped by this machine and the channel switches",
  "· 通道字母 ≠ 身体部位": "· Channel letters are not body parts",
  我已成年且自愿: "I'm 18+ and I want this",
  不再显示此提示: "Don't show this again",
  确认进入: "Enter",
  "第 {n} 层完成": "Floor {n} done",
  "已走 {n} 个节点 · 热 {heat} · 本局已自动存档":
    "{n} nodes · Arousal {heat} · run saved",
  "下行 ↓": "Descend ↓",
  "第 {f} 层 · 本层已走 {n} 节点": "Floor {f} · {n} nodes this floor",
  "第 {f} 层 · 第 {r} 房": "Floor {f} · Room {r}",
  "当前事件：{title}": "Now: {title}",
  "·行{r}": "·row{r}",
  "体感[{hint}]": "Feel[{hint}]",
  "描述你的行动……": "What do you do…",
  说出: "Speak",
  "回大厅（结束本局）": "Lobby (end run)",
  "地牢主正在写下这一房…": "The dungeon is writing this room…",
  展开描写: "Show text",
  跳过描写: "Skip text",
  "你选择了：「{chosen}」": "You picked: “{chosen}”",
  "{level} · 第 {tier} 层": "{level} · Floor {tier}",
  "第 {f} 层 · 房间 {r}": "Floor {f} · Room {r}",
  "HP {h} · 意志 {w}": "HP {h} · Will {w}",
  体感已清理: "Feel cleared",
  再开一局: "Play again",
  回大厅: "Lobby",
  本局足迹: "This run",
  场景: "Scene",
  片刻: "Beat",
  抉择: "Choice",
  深层: "Depth",
  终局: "Ending",
  "下次更新前不再提示": "Don't show again until the next update",
  // ---------- 审计补漏（第 4 轮） ----------
  "AI 模型配置": "AI model",
  内容版本说明: "About the content",
  完成: "Done",
  当前配置: "Current config",
  "进入地牢 ▶": "Enter dungeon ▶",
  连接失败: "Connection failed",
  连接成功: "Connected",
};

/** 翻译：zh 为代码内原文（默认语言），lang=en 时查词典。两分支都做 {var} 插值。 */
export function tr(zh: string, lang: UiLang, vars?: Vars): string {
  let out = lang === "en" ? (DICT[zh] ?? zh) : zh;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.split(`{${k}}`).join(String(v));
    }
  }
  return out;
}

/** 组件内翻译函数（语言随 state.lang 响应）。 */
export function useT(): (zh: string, vars?: Vars) => string {
  const lang = useUiLang();
  return (zh: string, vars?: Vars) => tr(zh, lang, vars);
}

/** 供词典扩展（工具脚本/测试用）。 */
export function addTerms(entries: Record<string, string>): void {
  Object.assign(DICT, entries);
}
