# dungeon_v2 · 开发指南（DEV_GUIDE）

> 引擎内长驻版，源自协作交接《D8-开发交接-fable.md》（2026-09-04）。D15 对照 D11 现行代码修订过时描述（GET render / unmet / theme_labels / effective_label / EN 切 / 前端已接）。改引擎/加内容前先读。
> 规格上游：协作交接\地牢\结论\S1（世界观）/ S3（字段定义）/ S2（事件表）/ S4（骰子）。
> 测试脚本：validate_pack / lint_words / selftest / autoplay（本目录），HTTP 与 zip 回归脚本在 协作交接\地牢\D6产出\tools\ 。
> 模块行数是 2026-09-04 D15 对照仓库的快照，只作量级；以文件为准。

# 〇、10 分钟上手（先读这一节）

1. **改内容还是改引擎？一句话判据**：你要写的东西能不能全部塞进 `content\pack\dungeon\<pack>\` 的 JSON 里、且不新增任何枚举值/effect 键/require 键/状态字段？能 → 内容级，不碰 Python；不能 → 引擎级，先读 §一.3 不变量再动手。
2. **读代码顺序**（约 3500 行 .py，1 小时读完）：`constants.py`（所有枚举与阈值）→ `engine.py::Engine.advance`（结算顺序，100 行）→ `effects.py` → `checks.py` → `schema.py`（validator，看它拒绝什么就知道格式是什么）→ `runtime.py`（HTTP 壳，含 GET render）→ `render.py`（前端看到什么，含 theme_labels / unmet）。其余按需。
3. **最快验证**（仓库根，任何控制台都行）：
   ```
   python -m backend.dungeon_v2.validate_pack content\pack\dungeon\zijin   # 0 error 才能加载
   python -m backend.dungeon_v2.lint_words    content\pack\dungeon\zijin   # 禁词 0 泄漏
   python -m backend.dungeon_v2.selftest                                  # 19/19（引擎回归，绑定 abyss 测试 fixture）
   python -m backend.dungeon_v2.autoplay [--pack DIR]                     # 四结局可达
   ```
4. **加一条事件的最小动作**：新建 `events/E0xx.json`（字段照 §二.A 表）→ 在某个现有事件的 `choices[]` 加一条 `next: "E0xx"` → 跑 validate + lint + autoplay。E017 样例 `D8产出\tools\e017_sample.py` 已跑通，照抄即可。
5. **别碰的东西**：§一.3 不变量；`safety.py`（体感唯一出口）；render 已有字段（只加不删，含 D11 的 `theme_labels` / `choices[].unmet` / `outcome.effective_label`）；`rng.variant_index` 公式。

---

# 一、架构交接

## 1.1 模块地图（20 个 .py + 本指南）

| 文件 | 行数 | 职责一句话 |
|---|---|---|
| `__init__.py` | 26 | 只导出 `DungeonRuntime` / `DungeonError`；模块地图注释 |
| `errors.py` | 23 | `DungeonError(code, zh, en)`，`str()`=`[code] 中文`；main.py 直接 `str(exc)` 回 400。`ContentError` = 包/校验错误 |
| `constants.py` | 98 | **所有枚举**（band/room/kind/settlement/intensity/feedback/dice/mark_stage）、**所有阈值**（ma 100/200/300/500、TN 6/8/10/12/14、ED6_ZERO_PCT=15、钳制范围）、render 映射表、effect/require 键白名单。改枚举只改这里 |
| `rng.py` | 68 | `RunRNG`（`random.Random` 包装，`get_state/set_state` 可 JSON 入档）；`variant_index`（SHA-256）；`seed_from_any` |
| `state.py` | 103 | `RunState` dataclass（§4.1 全部字段）+ `roll_new`（三维 1-10）+ `clamp_all` + `ma_tier`；`to_dict(en=)` 切骰子名/描述 |
| `effects.py` | 78 | `apply_effects(state, effects, visit_n, rng)`：grammar 归一、visit_n_eq 门、成长门、stage 指令、dice_gain、ability_up 忽略 |
| `checks.py` | 86 | `roll_bonus`（骰子）/ `resolve_check`（attr+骰≥TN）/ `split_require`（属性检定 vs 门槛）/ `unmet_gates_struct`（D11：`{key,need,current,text}`）/ `unmet_gates`（text 投影，兼容旧文案） |
| `schema.py` | 671 | **validator**：`validate_event` / `_validate_choice` / `_validate_fail` / `_validate_effects` / `validate_manifest` / `validate_theme` / `validate_bindings` / `validate_pack_graph` / `validate_tree`；`parse_feedback`；`ValidationResult(errors/warnings/notes)` |
| `loader.py` | 196 | 读包目录 → `load_tree` → `validate_tree` → `Pack`；`discover_packs` 只认 `manifest.json` 且 `format=dungeon_v2`，旧包静默跳过，单包失败隔离；`known_patterns_default` 从 `waveforms.py` 取波形中文名 |
| `narrative.py` | 40 | `select_variant`（idx 0=seed 基底，k=variants[k-1]）；`compose_text`（上一场 exit + trigger + 正文） |
| `feedback.py` | 163 | `FeedbackExecutor`：feedback 核心词 → bindings 动作模板（填 `$strength`）→ `safety.validate → send → safety.record`；`cleanup()`=clear+stop；±20% 扰动用独立 `random.Random()`；EN 走 `ui_en` |
| `engine.py` | 295 | `Run`（一局全部状态，可序列化；`snapshot(en=)`）、`Outcome`（含 D11 `effective_label`）、`Engine`（`new_run` / `enter` / `advance` / `choice_gate_view` 含 `unmet`）。**结算顺序在这里写死** |
| `save.py` | 61 | `data/saves/dungeon_v2/<slot>.json`：`{format, version, pack_id, seed, rng_state, run}`；旧档 `[save_format]` 拒绝；槽名白名单 |
| `render.py` | 147 | HTTP render：`event_view`（content_level/tier、choice disabled/check/`unmet`）、`feedback_view`、`outcome_view`（`effective_label`）、`theme_labels_view`（按 en 切）、`map_view`（chain）、`build` |
| `runtime.py` | 183 | `DungeonRuntime`：`to_state/render/start/advance/save/load/restart/_reload`；`_en()` 读 `cfg.character.lang`；急停拦截；先 cleanup 再执行新事件 feedback；`GET /render` 返回 `last_result` 只读 |
| `cli.py` | 17 | `utf8_console()`：CLI 入口切 UTF-8（GBK 控制台不崩） |
| `validate_pack.py` | 40 | 校验器 CLI，退出码 0/1/2 |
| `lint_words.py` | 142 | 禁词扫描 CLI（设备词/通道字母/波形名/全局禁词），退出码 0/1/2 |
| `selftest.py` | 697 | 19 项自测（**绑定 abyss 测试 fixture**，见 1.5 坑 9） |
| `autoplay.py` | 153 | 四结局可达搜索（`POLICIES` 策略表 + seed 扫描），`--pack` 可指向别的包 |

## 1.2 数据流

```
content/pack/dungeon/<id>/            backend/dungeon_v2/
  manifest.json ─┐
  theme.json     ├─▶ loader.load_tree ─▶ schema.validate_tree ─(0 error)─▶ loader.Pack
  bindings.json  │        │ utf-8-sig            │ errors → ContentError（整包拒绝）
  events/*.json ─┘        ▼                      │ warnings/notes → 日志
  base_setting.md   discover_packs ──────────────┘   （只认 format=dungeon_v2）
                          │
HTTP（main.py 地牢路由，D11 加了 GET render）   ▼
GET  /state  ──▶ runtime.to_state（active/packs/run/engine/pack_errors/estop/last_event）
GET  /render ──▶ runtime.render() 返回 last_result（D11 E1：刷新恢复；只读，不触发设备；无局 → [no_run]）
POST /start ──▶ runtime.start ──▶ Engine.new_run(seed)
                                    ├ RunRNG(seed) ──▶ RunState.roll_new（str/dex/int）   ← run RNG ①
                                    └ Engine.enter(start_event)
                                        ├ visits[eid]+=1 → visit_n
                                        ├ narrative.select_variant(seed,eid,visit_n)   ← SHA-256 ②（无 RNG）
                                        └ pending_feedback = parse_feedback(event.feedback)
POST /advance ─▶ runtime.advance
                  ├ safety.estop_active? → [estop]
                  ├ Engine.advance(run, choice)   ★ 结算顺序见 1.3-①
                  │     检定掷骰 ← run RNG ①      effects.dice_gain 抽池 ← run RNG ①
                  ├ FeedbackExecutor：cleanup?(败北/结局) → plan(bindings, event) → run()
                  │     $strength = band_strength×intensity_scale×(1±20%)  ← 独立 random.Random ③（不入档）
                  │     每条 safety.validate → send(backend.apply, dry_run 短路) → safety.record
                  └ render.build ──▶ {run, event, narrative, feedback, executed, dropped, map, outcome, theme_labels}
                     run.snapshot(en=) / theme_labels / dice_name·desc 按 cfg.character.lang==en 切
                     choices[].unmet[{key,need,current,text}]；outcome.effective_label（折叠后生效项）
POST /save ─────▶ save.write_save({pack_id, seed, rng_state ←①, run})
POST /load ─────▶ save.read_save → Run.from_dict → 不重放设备
POST /restart ─▶ runtime.restart（清 run/engine/last_result，不发设备命令）
```
**RNG 边界**：① run RNG（装配/开局 roll/骰子/dice_gain）**入档**，同 seed 同选择 → 同结果；② 变体选择用 SHA-256，无状态，跨进程复现；③ 数值扰动独立真随机，**不入档**，也**不消耗** ①（所以设备路径不影响骰子）。

## 1.3 关键不变量（写死的，后续不许破坏；每条给代码位置供复核）

| # | 不变量 | 代码位置 |
|---|---|---|
| ① | **结算顺序**：门槛不满足 → `[require_unmet]` 状态不变 → 属性检定（掷装备骰）→ 失败折叠 `fail.choice`（不二次检定）→ effects 逐条 → `clamp_all` → hp==0 且本次致 0 → 【清理】→ 败北回 `safe_room` 覆盖 next → 否则 `gate_check` 选项判 crossed → next==end → 【清理】先于锁定 → 否则 `enter(next)` | `engine.py::Engine.advance` L180-283；清理执行在 `runtime.py::_run_feedback`（cleanup 先于新事件 feedback） |
| ② | **钳制范围**：ma≥0（无上限）、hp/mp 0-10、str/dex/int 1-20、yin_hua/e_duo 0-100；每次 effects 后全量钳 | `state.py::RunState.clamp_all`；常量 `constants.py` MA_MIN/HP_MAX/MP_MAX/ATTR_MIN/ATTR_MAX/AXIS_* |
| ③ | **fail 防递归**：`fail.choice` 不能指向自己、不能指向另一条属性检定；折叠后直接应用目标 effects/next/estop，不再检定、不查目标门槛 | validator `schema.py::_validate_fail`；运行时 `engine.py` 折叠分支不再调 `resolve_check` |
| ④ | **变体 = SHA-256**：`int.from_bytes(sha256(f"{seed}\|{event_id}\|{visit_n}")[:8],"big") % N`；N≤1 恒 0；禁内置 `hash()` | `rng.py::variant_index`；selftest t03/t04 双进程比对 |
| ⑤ | **safety 唯一出口**：任何设备动作必须 `safety.validate` 拿 cmd → `send` → `safety.record`；dry_run 或无 send 不发；急停由 safety 自拒 | `feedback.py::FeedbackExecutor.run`；不存在任何绕过路径（D5 D3 复核） |
| ⑥ | **fail-closed**：未知字段/枚举值/effect 键/require 键 → error → 整包拒绝加载；warning/note 不阻断 | `schema.py` 全部 `res.error(...)`；`loader.py::load_pack` 有 error 抛 ContentError |
| ⑦ | **枚举冻结**：band 5 / room 9 / kind 5 / settlement 13 / intensity 5 / feedback 核心词 6 / dice 4 / mark_stage 5；theme.bands、theme.feedback_labels、bindings.band_strength/intensity_scale/rhythm 必须**恰好**覆盖对应枚举 | `constants.py`；`schema.py::validate_theme/validate_bindings`（`set(x) != set(C.X)` 即 error） |
| ⑧ | **estop 语义**：`estop_overrides` 是内容标注（急停仍停，告知安全层/前端），引擎不据此放行任何东西；急停中 `advance` 一律 `[estop]` 拒绝；yield/end_sink 未标 → warning，defeat 未标 → note（2026-09-04 拍板） | `runtime.py::advance` 首行；`schema.py::_validate_choice` |
| ⑨ | **visit_n / visit_n_eq**：`visit_n` = 本事件第几次进入（第 1 次=1），进入即 +1；effect 带 `visit_n_eq: N` 仅 visit_n==N 生效；variants 轮转与 visit_n_eq 两层独立 | `engine.py::Engine.enter`；`effects.py::apply_effects` |
| ⑩ | **三维成长仅 visit_n=1**：str/dex/int 的任何 delta（正负）只在首访生效；ma/yin_hua/e_duo/hp/mp 每次生效 | `effects.py` `if key in C.ATTRS and visit_n != 1: skip` |
| ⑪ | **ed6 15% 归零**：先 `randint(0,6)` 再独立 `random() < 0.15`，归零 = total 整体为 0（必失败）；RNG 消费顺序固定 | `checks.py::roll_bonus`；`constants.ED6_ZERO_PCT` |
| ⑫ | **crossed_gate** 只在 `gate_check: true` 的选项结算后判：`mark_stage ≥ form ∧ ma ≥ 100`；未 crossed 走 `next_uncrossed`；只锁本局 | `engine.py` 步骤 5；`constants.GATE_STAGE_MIN/MO_HUA_BUFFER` |
| ⑬ | **render 只加不删**：基线 `run/event{id,title,theme_id,kind,content_level,tier,choices[{id,label}],free_input}/narrative/feedback{hint}/executed/dropped/map`；D11 已加 `theme_labels`、`choices[].unmet[{key,need,current,text}]`、`outcome.effective_label`、`run.dice_name/dice_desc` 按 en 切。`run` 不含 rng_state | `render.py::build/event_view/theme_labels_view`；`runtime._en` |
| ⑭ | **存档**含 `format/version/seed/rng_state`；旧档拒绝无迁移；目录与旧引擎分离 | `save.py` |

## 1.4 测试套件

### 五条命令（仓库根；GBK 控制台也行，CLI 自带 utf8_console）
| 命令 | 退出码 | 看什么 |
|---|---|---|
| `python -m py_compile backend\dungeon_v2\*.py` | 0 | 语法 |
| `python -m backend.dungeon_v2.validate_pack <pack_dir>` | 0/1/2 | `x error / y warning / z note`；1 = 会被拒绝加载；2 = 目录/JSON 读不出 |
| `python -m backend.dungeon_v2.lint_words <pack_dir>` | 0/1/2 | `LEAK <位置>: <词>`；扫 seed/variants/trigger/title/note/feedback/choices/flags/theme/bindings 说明/base_setting/引擎 EN 文案 |
| `python -m backend.dungeon_v2.selftest [--pack DIR] [--probe SEED]` | 0/1 | 19 项；`--probe` 只打变体探针（跨进程比对用） |
| `python -m backend.dungeon_v2.autoplay [--pack DIR] [--seeds N]` | 0/1 | 四行「结局汇总」；不可达=1 |

### 集成两件（D6 已验证，脚本可复跑）
- HTTP：仓库根 `DGLAB_DRY_RUN=true python -X utf8 -c "import uvicorn; from backend.main import app; uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning')"`，另开终端 `python -X utf8 协作交接\地牢\D6产出\tools\http_smoke.py --base http://127.0.0.1:8765`（39 断言）。**用 8765 不用 8000，跑完 kill**。
- zip 安装：`python -X utf8 协作交接\地牢\D6产出\tools\zip_install_check.py`（17 项，全在 %TEMP%）。

### 新增内容后必须重跑什么（最低要求）
| 改了什么 | 必跑 | 说明 |
|---|---|---|
| 只加/改事件 JSON、theme、bindings、base_setting | `validate_pack` + `lint_words`（新包）+ `autoplay --pack`（新包）+ `selftest`（**abyss 测试 fixture**） | selftest 绑定 abyss 测试 fixture（t01 断言事件数==16，t07/08/10/11/18 写死路径），改过的包跑它会假 FAIL；它的作用是证明引擎没被你顺手改坏 |
| 改了主线路径（现有 choice 的 next/序号/effects 数值） | 上面四件 + **更新 `selftest.py` 的路径断言与 `autoplay.POLICIES`** | 见 §二.A.7 |
| 改了 `backend/dungeon_v2/*.py` | 五条命令全跑 + HTTP 冒烟 | 引擎级改动还要按 §一.3 逐条对不变量 |
| 改了 constants 枚举 | 以上全部 + theme/bindings 同步（否则 validator 恰好覆盖检查直接 error） | |

## 1.5 已知取舍与坑

1. **pulse_hold 不接**：main.py 只给 `executor.send = backend.apply`，循环波形要走 `backend.start_pulse_hold`（`device/base.py`），所以 bindings 禁用 pulse_hold（validator 直接 error），「持续」= 8s pulse + hold_strength。要真持续：给 runtime 一个 backend 引用并在 `FeedbackExecutor.run` 加 `pulse_hold` 分支 → `backend.start_pulse_hold`，再放开 `constants.FEEDBACK_ACTION_OPS` 与 validator。
2. **LLM 不接**：`cfg.dungeon.ai_narrative` 忽略，`runtime.llm` 只存不用；叙事恒为作者 seed/variant。接的话在 `render.build` 前对 `text` 做扩写，`narrative.source` 加值 `"llm"`。
3. **dry_run**：`safety.dry_run`（来自 cfg.app.dry_run / 环境变量 `DGLAB_DRY_RUN`）为真时 executor 只 record 不 send；仓库 config.yaml 是 `dry_run: false`，**测试务必设 `DGLAB_DRY_RUN=true`**。
4. **存档目录分离**：`data/saves/dungeon_v2/` vs 旧 `data/saves/dungeon/`；旧档无 format 标记 → `[save_format]` 拒绝，无迁移。`SAVE_VERSION` 不等 → `[save_version]` 拒绝（升级策略见 §二.B.5）。
5. **GBK 控制台**：所有 CLI `main()` 首行 `cli.utf8_console()`；错误文案不再含 `∉`。运行链请仍用 `python -X utf8`（uvicorn 日志里的非 GBK 字符会被 logging 吞成「Logging error」不崩，但难看）。
6. **BOM**：loader 全部 `utf-8-sig`；save.py 仍 `utf-8`（存档是我们自己写的）。
7. **warning → note**：validator 三级：error 拒绝 / warning 提示 / note 备案（目前只有「defeat 未标 estop 可免」一条）。按 warning 行数判的脚本要知道这点。
8. **`feedback` 在进入事件时执行**，不是选选项时；败北/结局的清理在锁定前额外执行一次。读档不重放设备。
9. **selftest 绑定 abyss 测试 fixture**（`backend/tests/fixtures/dungeon_v2/abyss`）：`t01` 断言事件数 16、`t02` 用 E003/E002/E004/E006/E008/E012/E005/E016 做坏样例、`sink_choices()` 与 `t08/t10/t11/t18` 写死选项序号与去向、`t14` 断言 E001 tier=1/lvl=1 与 E006 是第 4 步。这是有意的回归锚点，不是通用包测试；改包主线就要同步改它（§二.A.7）。
10. **autoplay 策略表 hardcode**：`POLICIES[target][event_id] = choice 序号`；新事件若在主线上而策略没覆盖 → `策略未覆盖事件 E0xx` 判不可达（FAIL）。叶子分支（现有选项不指向它）不受影响。
11. **单安全区**：`manifest.safe_room` 只有一个，败北一律回它；多安全区要改引擎（§二.B.3）。
12. **E012 未 crossed 留在主巢**（`next_uncrossed: "E012"`，visit_n 递增走 v2）是我拍的板，S2 原文没给去向；想改成独立事件只改 E012 的 `next_uncrossed`。
13. **败北判据**是「hp==0 且本次致 0」，hp=0 空手闲逛不重复败北（`engine.py` 步骤 4 `hp_before > 0 or hp_hit`）。
14. **前端已接 dungeon_v2**（D7 面板 + D11 契约 + D14 验收通过）：`DungeonPanel.tsx` 走 `./dungeon/`（Lobby / RunView）；`api.dungeonRender()` 打 `GET /api/dungeon/render` 做刷新恢复；显示名优先 `render.theme_labels`，本地 `labels.ts` 只回退。**已无 `DUNGEON_PLAYABLE=false`。** 产品铁律仍在面板头注释：急停红条、不渲染设备强度/通道/波形名、成年锁沿用 ConsentModal。
15. **EN 切**：`runtime._en()` = `cfg.character.lang == "en"`。影响 `run.snapshot(en=)` 的骰子名/描述、`theme_labels.dice`、`feedback.hint`（走 `ui_en`）。中文默认。切语言走既有 `POST /api/character/lang`，地牢不另开路由。

---

# 二、内容扩展指南

## A. 更多事件（E017+，内容级，不动引擎）

### A.1 一条新事件从写到上线（逐步清单）
1. **定位**：决定 band（入口/中层/上带/下带/终点）与 room/kind，看 A.3 分配原则。
2. **写 `events/E0xx.json`**（文件名 stem == id，`E` + 三位数字），字段照 A.2 表。
3. **接入空间链**：在某个现有事件的 `choices[]` 里加一条 `next: "E0xx"`（≤4 条/事件），或改一条现有 choice 的 `next`（改主线要同步 A.7）。新事件自己的每条 choice 都要有合法 `next`（已知 id 或 `end`，后者只允许 kind=ending）。
4. **跑校验**：`validate_pack` 0 error；`lint_words` 0 泄漏。
5. **跑可达**：`autoplay --pack <你的包>` 四结局仍可达（新事件在叶子上无需改策略；在主线上要改 `POLICIES`）。
6. **跑引擎回归**：`selftest`（abyss 测试 fixture）19/19。
7. **实走一遍**：用 `Engine` 直接走到新事件（`debug_state` 可把属性拉满/拉空验证检定两支），或起后端用 HTTP 点过去。样例见 `e017_sample.py` 步骤 5。
8. **设备节奏**：feedback 核心词决定 bindings 用哪组动作；不要为单个事件在 bindings 里加特例——bindings 是全包共用的六组模板。

### A.2 字段怎么写 / validator 查什么
| 字段 | 写法 | validator 事件级检查 |
|---|---|---|
| `id` | `"E017"` | 形如 `E\d{3}`；等于文件名 stem；全包唯一（同名 json/yaml 报重复） |
| `title` | 非空 | |
| `band` | entry/mid/upper/lower/end | 枚举；`end` 只允许 kind=ending |
| `room` | gate/corridor/encounter/nest/rest/treasure/trap/boss/ending | 枚举；`rest⇔kind rest`、`boss⇔kind boss`、`ending⇔kind ending` 双向绑定 |
| `kind` | scene/beat/rest/boss/ending | 枚举；rest/ending 的 intensity 必须 none，feedback 必含「清理」 |
| `intensity` | none/low/medium/medium-high/high | 枚举 → render content_level 0-4 |
| `species` | `"无"` 或种族名（哥布林/触手/牛头人/…） | 非空字符串；参与包级「连续三场同 species」排重（「无」不算） |
| `trigger` | 一句：玩家做了什么本事件开始 | 非空 |
| `seed` | 正文（**不写数字/百分比/设备词**） | 非空；lint 扫禁词 |
| `checks` | `["dex","str"]` 本场用到的属性 | 列表、∈ str/dex/int、不重复；choices 里所有属性检定键必须 ⊆ checks |
| `settlement` | `["escape","yield","kill"]` | 非空列表、∈ 13 枚举；choices 的 settlement 必须 ∈ 此列表 |
| `choices[]` | 2-4 条（ending 1-4） | 见下 |
| `feedback` | `"试探→持续"`、`"无或试探"`、`"连击（短，必须可停）"` | 至少含一个核心词（无/试探/持续/连击/停顿/清理），按出现顺序执行；修饰语随意；入口带出现 持续/连击 → warning |
| `variants` | `["v2 正文","v3 正文"]`（可选） | 非空字符串、≠ seed；>3 条 warning。**未写/空 = 单版** |
| `flags` | `{"reinforcement":"说明","estrus":"说明"}`（可选） | key 英文小写标识，值字符串。首批白名单只有这两个 key（引擎只是存进 `run.state.flags`，不解释） |
| `note` | 字符串（可选） | lint 扫禁词 |
| `free_input` | `false`（可选） | 首批只允许 false |

**choice 字段**：
| 字段 | 写法 | 检查 |
|---|---|---|
| `label` / `exit` | 非空；label=身体动作，exit=空间上一句（会拼到下一事件正文前） | |
| `settlement` | ∈ 事件 settlement 列表 | ending 事件只能 end_escape/end_stay/end_sink；非 ending 不得用 |
| `next` | 已知事件 id；ending 事件写 `"end"` | 悬空 → error |
| `require` | 属性检定 `{"dex": 10}`（**最多一个属性键**）或门槛 `{"stage_min":"appear"}` / `{"yin_hua_gte":50}` / `e_duo_gte/ma_gte/hp_gte/mp_gte` | TN 1..20 整数；超出层带区间 warning；`mo_hua_gte` 拒绝；属性键必须在事件 checks |
| `fail` | 属性检定**必填**：`{"choice": 2}`（1-based，不能指自己、目标不能是属性检定）或 `{"next","settlement","exit"}` | 无检定不得写 fail |
| `effects` | `{"ma":5,"dex":1,"stage_appear":true}` 或列表 `[{"ma":10,"visit_n_eq":1},{"yin_hua":5}]` | delta 键非零整数；stage_*/dice_gain 只允许 true；visit_n_eq ≥1；只有 visit_n_eq 没实际修改 → error；未知键 error |
| `estop_overrides` | `true`（yield/end_sink 建议必标） | bool |
| `note` | 可选 | |
| `gate_check` + `next_uncrossed` | 只给「沉沦判定入口」用（首批 E012 选1）；成对出现 | 非 boss 事件用 → warning |

### A.3 bands 分配原则（S1 §三 + S3 §四 + bindings）
| band | TN 区间（validator 建议区间，超出 warning） | intensity 常用 | feedback 节奏约定 | bindings 基准强度 |
|---|---|---|---|---|
| entry | 6-8 | none/low | 无 / 试探 / 停顿（出现 持续/连击 warning） | 8 |
| mid | 6-8 | low/medium/medium-high | 试探→持续；安全区 = 清理 | 14 |
| upper | 8-10 | medium/medium-high | 持续（群攻交替）；岔口/陷阱 = 停顿 | 20 |
| lower | 10-12 | high | 持续→连击（短，必须可停） | 26 |
| boss（room=boss，band 一般 lower） | 14-15 | high | 突袭后持续 | 26 |
| end | 任意（无检定） | none | 清理（必须） | 0 |
`$strength = band_strength × intensity_scale(none0/low.6/medium.8/mh1.0/high1.2) × (1±20%)`，再钳到安全层上限。所以「更重」= 换 band 或 intensity，不是改 bindings。

### A.4 variants 何时写
- N≥2 才写（列表只放 v2/v3…，基底就是 seed）；高频/可重访事件（安全区、岔口、Boss、宝藏重访匣空）写 2-3 条，低频一次性事件不写。
- 索引由 `sha256(seed|event_id|visit_n) % N` 决定，**不是** visit_n 直接选 v2——所以 v2/v3 都要能独立成立，别写「第二次来」这种绝对措辞（写「这间你来过」这种相对措辞可以，因为 visit_n=1 时也可能抽到 v2？——**不会**：N=2 时 visit 1 有 50% 抽到 v2）。结论：**variants 里的重访措辞要写得首访读到也不穿帮**，或者只在明确会重访的事件（E006/E008/E012）用重访措辞并接受首访偶发。这是当前算法的固有取舍，改它要动 `rng.variant_index`（不变量④），不建议。
- 状态尾句（喘匀了/纹还烧着）并入 variants，不单做 overlay。

### A.5 空间链扩展规则（包级图检查怎样约束你）
`schema.validate_pack_graph` 把每个 choice 的 `next`、`next_uncrossed`、`fail.next` 都当边，然后查：
| 检查 | 触发 error 的情况 | 加一条事件不触发的最小要求 |
|---|---|---|
| 从 `start_event` 可达 | 新事件没有任何入边 | 至少一个现有 choice `next` 指向它 |
| 每个事件能到达某个 ending | 新事件所有出边都绕回不了 Boss | 至少一条 choice 的 next 最终能走到 E012（首批唯一 Boss） |
| 结局前驱必须是 boss | 非 boss 事件的 choice 直接 `next` 到 E013/E014/E015 | 新事件不要直连结局；想加新结局 → 也得从 Boss 出边进（或加新 Boss） |
| `start_event` 在 entry 带、`safe_room` 是 kind=rest | 改 manifest 指向不合规事件 | 不改 manifest 就不会碰 |
| 连续三场同 species | A→B→C 三个**不同**事件 species 相同（同事件自环不算） | 新事件 species 与它入边事件、出边事件不要三连同种；写「无」最省事 |
| 至少一个 boss、一个 ending | 删事件才会碰 | |
| kind=rest 的 feedback 含清理 / intensity none | 新安全区忘写 | 第二安全区照 E006 抄 |
另有 warning：缺 escape/stay/sink 某类结局；没有任何 gate_check 选项。

### A.6 现有引擎「不改代码」就能做的「更大」
- **每个 band 塞更多事件**：单纯加节点+改 next，无上限（choices ≤4/事件是唯一分叉限制，靠多层岔口事件展开）。
- **第二/第三条支线**、**多个 Boss**（room=boss；结局前驱是任一 boss 即可）、**新结局**（kind=ending，从 boss 出边进）。
- **第二安全区（休息点）**：可以加 kind=rest 事件，但**败北仍只回 manifest.safe_room**（引擎单安全区，§B.3）。
- **重访门/一次性奖励**：`visit_n_eq`；**分档解锁**：`stage_min` / `*_gte` 门槛。
- **新 species**：任意字符串，只影响三连排重。
- **新 flags key**：小写英文即可，引擎只存。

### A.7 改主线时要同步的测试代码（这是唯一需要碰 .py 的内容级改动）
- `autoplay.POLICIES`：四张 `{event_id: choice 序号}`，新主线事件加进去；序号变了要改。
- `selftest.py`：`t01` 事件数 16；`sink_choices()`；`t02` 坏样例引用的事件/选项；`t08`（E012 未 crossed 三次）、`t10`（败北路径）、`t11`（净化窗口路径 ma 合计）、`t13`（走到 E011 存档）、`t14`（E001→E002→E005→E016→E006 四步）、`t18`（E016 路径）、`t19`（E003 选1/选3）。建议把路径抽成常量再改。
- `D6产出\tools\http_smoke.py`：败北用 seed 37 + defeat 策略 28 步、沉没用 `SINK` 十步——数值一变要换 seed。

### A.8 自证（E017 样例，已跑通）
`D8产出\tools\e017_sample.py`：复制 abyss 到 %TEMP% → 写 `E017 上带·暗龛`（int 9 检定 + fail 折叠 + 列表 effects 含 visit_n_eq）→ 给 E008 加第 4 条 choice → E017 → 跑四件套 + 引擎实走。结果：
```
validate_pack(新包)  0 error / 0 warning / 3 note  exit 0   （事件数 17）
lint_words(新包)     0 处泄漏                       exit 0
autoplay(新包)       四结局可达                     exit 0   （E017 是叶子分支，POLICIES 无需改）
selftest(仓库原包)   19/19                          exit 0
引擎实走             int 20 → 成功 → E006；int 1 → 失败折叠选 2 → ma=5 yin_hua=2 → E011
```
第一次跑我把 selftest 指向了新包 → `t01: 事件数 17 != 16` 假 FAIL，这就是坑 9 的现场；脚本已改为对原包跑。

## B. 更大的地图（引擎级，方案不实现）

### B.1 现状边界
- 空间 = **固定有向图**：16 个事件，每条 choice 的 `next` 硬编码；「装配」目前只有开局三维 roll 和骰子，**没有从池子抽事件**。
- `render.map` 是 `mode:"chain"` 的节点表（全部事件 + visited/current），前端把它画成一条链。
- band 是 5 个冻结枚举；tier 1-5 由 band 直接映射；bindings 强度按 band 查表。
- 单 `safe_room`，败北只回它。
差距：要「更大」到玩家两局走的不是同一条路，需要 **next 可以是「从某个池子抽」**；要「更深」需要 band 可扩或 band 内多房间串联；要「更多安全区」需要最近安全区算法。

### B.2 蓝图一：band 事件池 + PRNG 装配（推荐，兼容现包）
**目标**：choice 的 `next` 允许写 `"$pool:<band>"`（或 `"$pool:<tag>"`），运行时用 run RNG 从该池抽一个事件进入，优先未访问（T037 去重），排掉与最近两场同 species 的候选。abyss 不用池 → 行为完全不变。

| 层 | 改动点（文件::函数） | 内容 |
|---|---|---|
| 格式 | `manifest.json` 新增可选 `pools: {"<name>": {"members": ["E0xx",...], "prefer_unvisited": true, "exclude_species_streak": 2}}` | 池成员显式列出（比按 band 自动收集稳，validator 好查） |
| 常量 | `constants.py` 新增 `POOL_PREFIX = "$pool:"` | |
| validator | `schema.py::validate_manifest` 查 pools 成员是已知 id、不含 ending/rest/boss（安全区和结局不进池）；`_validate_choice` 里 `next` 允许 `$pool:<name>` 且 name ∈ pools；`_edges()` 把 `$pool:X` 展开为到全部成员的边（可达/可结局/结局前驱检查自然成立）；「连续三场同 species」对池边只 warning（运行时去重兜底） | |
| loader | `loader.py::Pack` 加 `pools: dict[str, list[str]]` 属性（从 manifest 读） | |
| engine | 新增 `engine.py::Engine._resolve_next(run, next_id) -> str`：非 `$pool:` 原样返回；是 → 候选 = 成员 −（prefer_unvisited 时已访问者，若全访问过则不过滤）−（最近 `exclude_species_streak` 场同 species）→ `run.rng.choice(candidates)` → 记 log `{"type":"assemble","pool":X,"picked":eid,"candidates":[...]}`。在 `advance` 步骤 6 和败北/gate 之后调用一次；`fail.next` 也过它 | 用 **run RNG**（不变量①的 RNG 边界）：同 seed 同选择 → 同装配，跨进程/读档一致；**消费顺序**：检定掷骰 → dice_gain → 装配，写进注释并加 selftest |
| 装配可达性 | `autoplay.play` 已按事件 id 查策略，不用改；`find_seed` 扫 seed 即覆盖不同装配 | `selftest` 加：同 seed 两局装配序列相同；PYTHONHASHSEED 不同的两个进程装配序列相同（沿用 t04 的子进程模式） |
| render | `render.map_view` 加 `"pools": {name: members}`，节点加 `pool` 字段；`mode` 仍 chain（前端可只画已访问路径） | 只加字段 |
| 存档 | `Run` 不新增字段（装配结果已体现在 `event_id/visits/log`），`SAVE_VERSION` 不变 | |
| 兼容 | abyss 无 `pools`、无 `$pool:` → 零行为变化；validator 对无 pools 的包跳过池检查 | |

### B.3 蓝图二：多安全区 + 最近安全区（S3 §五已写算法）
| 改动点 | 内容 |
|---|---|
| `manifest.json` | `safe_room` 保留（兼容）+ 新增可选 `safe_rooms: ["E006","E0xx"]`；validator 查每个都是 kind=rest |
| `loader.Pack.safe_rooms` | 列表属性，缺省 `[safe_room]` |
| `engine.py` 新增 `_nearest_safe(run) -> str` | 以当前 `run.event_id`（败北发生的事件）为起点，对 `schema._edges(pack.events)` 做 BFS 取最短边数；同距取 `TIER_BY_BAND` 更小者（越靠出口越优先）；池边按展开后的成员算 |
| `advance` 步骤 4 | `self.enter(run, self._nearest_safe(run), prefix=defeat_line)` 替代 `pack.safe_room` |
| 测试 | selftest 加：从下带败北回下带安全区、从中层败北回 E006 |

### B.4 蓝图三：扩 band（不推荐先做）
band 是冻结枚举，牵一发动全身：`constants.BANDS/TIER_BY_BAND/TN_BAND_RANGE` → `theme.bands`、`bindings.band_strength`（恰好覆盖检查）→ `render.tier`（前端 1-5 假设）→ S1 层带定义本身。**替代**：在现有 5 band 内用 `room` + 多个事件串联表达「更深」；真要扩，先改 S1 拍板，再按上面清单一次改齐并 bump `PACK_FORMAT_VERSION`。

### B.5 版本与兼容策略
- **包格式**：新增可选字段不 bump `PACK_FORMAT_VERSION`（loader 对缺省宽容）；改语义/删字段才 bump，并让 `validate_manifest` 对旧版本给可读 error。
- **存档**：`Run.from_dict` 对新增字段用 `d.get(k, default)`，不 bump `SAVE_VERSION`；改现有字段语义才 bump，旧版本 `[save_version]` 拒绝（当前策略：拒绝、不迁移，与 D2 一致）。
- **回归底线**：五条命令 + HTTP 冒烟 + selftest 新增「装配复现」两项；三结局可达由 autoplay 扫 seed 覆盖（策略表按事件 id，池装配不影响）。

### B.6 哪些「更大」不用改引擎（对照）
| 需求 | 现有引擎 | 要改 |
|---|---|---|
| 每 band 更多事件 / 更多支线 / 多 Boss / 新结局 | ✅ 纯内容 | — |
| 休息点（非败北回点） | ✅ kind=rest 事件 | — |
| 每局路线随机（抽事件） | ❌ | B.2 |
| 败北回最近安全区 | ❌ | B.3 |
| 第 6 个层带 | ❌ | B.4 |
| 第二张地图/双轴 | ❌（S1 拍板单向下探） | 先改设定 |

## C. 更多装备

### C.1 新骰子（例：d10）
| 改动点 | 内容 |
|---|---|
| `constants.py` | `DICE += ("d10",)`；`DICE_MAX_BONUS["d10"]=10`；`DICE_NAME_ZH/EN`、`DICE_DESC_ZH/EN` 各加一条；是否进 `DICE_DROP_POOL`（见平衡） |
| `checks.py::roll_bonus` | **不用改**：按 `DICE_MAX_BONUS[dice]` 掷 `randint(0, N)`；只有 ed6 是按名字特判的归零逻辑。想给新骰特效（如 d10 掷满再掷）在这里加 `if dice == "d10"` 分支，并保持 RNG 消费顺序可复现 |
| `state.py` | 不用改：`clamp_all` 用 `C.DICE` 校验，`to_dict` 用 `DICE_NAME_ZH[self.dice]` |
| `effects.py` | 不用改：`dice_gain` 从 `DICE_DROP_POOL` 抽。若要**定向发放**（`dice_gain: "d10"`），改 `apply_effects` 的 dice_gain 分支接受字符串 ∈ `C.DICE`，并改 `schema._validate_effects`（目前只允许 `true`） |
| `schema.py` | 事件里没有 dice 枚举字段，无改动（除上面定向发放） |
| `bindings.json` | 不涉及（骰子不影响体感） |
| `render.py` | 不用改：`run.dice/dice_name/dice_desc` 由 state.to_dict 带出；前端 HUD 若按 4 种写死要加 |
| `selftest` | `t05` 遍历 `DICE_MAX_BONUS` 自动覆盖新骰区间；`t06/t18` 断言掉落覆盖 `set(DICE_DROP_POOL)`，进池即自动要求可抽到 |
| `lint_words` | `scan_engine_en` 自动扫新 desc |
**平衡提醒**：TN 分档（6/8/10/12/Boss 14-15）按 `attr 1-10 + 0~6` 的 1~16 区间定的。d10 上限 attr+10：Boss TN 14 在 attr=4 就能摸到，极难 12 在 attr=2 可过，「Boss 才需要硬扛」的设计失效；层带递进（中 6-8/上 8-10/下 10-12）被抹平。建议：d10 **不进 E016 掉落池**，只作下带专属掉落或消耗品；或引入「骰面越大归零率越高」（复用 ed6 机制，`ED6_ZERO_PCT` 泛化成 `DICE_ZERO_PCT: dict`）。S4 明确「不做 d8」就是这个理由。

### C.2 新道具类型（非骰子，例：一次性护符 `ward`）
**字段级扩展点**：
| 层 | 改动 |
|---|---|
| `state.py::RunState` | 新字段 `items: list[str] = field(default_factory=list)`（或 `dict[str,int]` 计数）；`from_dict` 加 `s.items = list(d.get("items") or [])`（缺省宽容，不 bump SAVE_VERSION）；`to_dict` 自动带出 |
| `constants.py` | `ITEMS = ("ward", ...)` 枚举 + `ITEM_NAME_ZH/EN`、`ITEM_DESC_ZH/EN`；`EFFECT_FLAG_KEYS += ("item_gain", "item_use")`；如需门槛 `REQUIRE_GATE_KEYS += ("has_item",)` |
| `effects.py::apply_effects` | 新分支：`item_gain: "ward"` → append（可配 `visit_n_eq` 做一次性拾取，与 E016 骰子同法）；`item_use: "ward"` → 若持有则移除并应用该道具效果，否则 skipped |
| `schema.py::_validate_effects` | 允许 `item_gain/item_use` 值 ∈ `C.ITEMS`；`_validate_choice` 的 require 分支允许 `has_item: "<id>"`（纯门槛，不掷骰、无 fail） |
| `checks.py::unmet_gates` | `has_item` → `v not in state.items` 则「需持有 <name>」 |
| `engine.py` | 只有「被动触发型」道具需要碰：如护符「hp 归零改为 1 并消耗」放在步骤 4 判败北之前：`if run.state.hp == 0 and "ward" in run.state.items: run.state.items.remove("ward"); run.state.hp = 1; log`。主动使用型走 effects 不碰引擎 |
| `render.py` | `run.items` 自动带出；`event_view` 的 choice `require` 已透传 `has_item` 给前端灰显（门槛不满足时同时带 `unmet`）；HUD 展示由前端读 `run.items` + 名称表（可在 `state.to_dict` 顺手带 `items_view: [{id,name,desc}]`） |
| `lint_words.scan_engine_en` | 加扫 `ITEM_DESC_*` |
| `selftest` | 新增：拾取一次性（visit_n_eq）、使用消耗、门槛拒绝、护符救命一次且消耗、读档保留 items |
**最小示例**（内容侧）：
```jsonc
// 宝藏事件拾取（仅首访）
"effects": {"item_gain": "ward", "visit_n_eq": 1}
// 某遭遇的选项，需持有护符才可选，选了就消耗
"require": {"has_item": "ward"}, "effects": {"item_use": "ward", "ma": -5}
```

### C.3 `dice_gain` / `visit_n_eq` 如何复用
- **一次性拾取** = 任意 `*_gain` effect 配 `visit_n_eq: 1`（引擎已实现门，validator 已接受），重访自然不给；配 variants 写「匣空」重访版。
- **重访门** = `visit_n_eq: 2/3` 让某效果只在第 N 次触发（如第二次回祭坛才出现的 NPC 线）。
- **随机抽一件** = 照 `dice_gain` 的写法：`rng.choice(POOL)` 用 run RNG（入档、可复现），不要用 `random`。
- **替换 vs 累加**：骰子栏是单槽替换（`state.dice = new`）；道具建议列表累加，消耗时 remove。

---
