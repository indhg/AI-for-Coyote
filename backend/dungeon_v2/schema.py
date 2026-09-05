# -*- coding: utf-8 -*-
"""内容格式校验器（fail-closed）。

校验对象是「已读入内存的包树」：
    tree = {
      "manifest": dict, "theme": dict, "events": {event_id: dict},
      "bindings": dict, "base_setting": str,
    }
任何 error → 包拒绝加载。warning 只报告不阻断。note = 已拍板的备案说明（不需处理）。
规则清单见交付文档 §二（新 schema 与校验规则）。

事件格式（events/E0xx.json）：
    id / title / band / room / kind / intensity / species / trigger / seed
    checks: [attr...]            本场用到的属性（choices 里的属性检定必须 ⊆ checks）
    settlement: [enum...]        本场合法出口（choices 的 settlement 必须 ∈ 此列表）
    choices: [{label, settlement, next, exit,
               require?, effects?, fail?, note?, estop_overrides?,
               gate_check?, next_uncrossed?}]
    feedback: "试探→持续"        核心词 ∈ 无/试探/持续/连击/停顿/清理，修饰语随意
    flags?: {key: "说明"}        key=英文标识
    variants?: ["v2 文本", ...]  多版；未写/空 = 单版
    note?: "..."
    free_input?: false           首批固定 false
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import constants as C

_PACK_MODE = C.PACK_MODE_CHAIN  # validate_tree 写入；choice.next 允许 map

_EVENT_ID = re.compile(r"^E\d{3}$")
_FLAG_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_PACK_ID = re.compile(r"^[a-z][a-z0-9_\-]*$")

EVENT_REQUIRED = ("id", "title", "band", "room", "kind", "intensity", "species",
                  "trigger", "seed", "checks", "settlement", "choices", "feedback")
EVENT_OPTIONAL = ("flags", "variants", "note", "free_input")
CHOICE_REQUIRED = ("label", "settlement", "next", "exit")
CHOICE_OPTIONAL = ("require", "effects", "fail", "note", "estop_overrides", "gate_check", "next_uncrossed")
MANIFEST_REQUIRED = ("format", "format_version", "id", "title", "themes", "version",
                     "start_event", "safe_room", "events_dir", "theme_file", "bindings_file",
                     "base_setting_file")
BINDINGS_REQUIRED = ("format", "channels", "band_strength", "intensity_scale", "rhythm")

_CORE_PATTERN = re.compile("|".join(map(re.escape, C.FEEDBACK_CORE)))


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)      # 已拍板备案，不需处理

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    def note(self, where: str, msg: str) -> None:
        self.notes.append(f"{where}: {msg}")

    def report(self) -> str:
        lines = []
        for e in self.errors:
            lines.append(f"ERROR   {e}")
        for w in self.warnings:
            lines.append(f"WARNING {w}")
        for n in self.notes:
            lines.append(f"NOTE    {n}")
        lines.append(
            f"结果：{len(self.errors)} error / {len(self.warnings)} warning / {len(self.notes)} note"
            f" → {'OK' if self.ok else 'REJECT'}"
        )
        return "\n".join(lines)


# ---------- feedback 解析 ----------
def parse_feedback(text: str) -> list[str]:
    """从 feedback 字符串按出现顺序抽核心词（去重保序）。"""
    found: list[str] = []
    for m in _CORE_PATTERN.finditer(str(text or "")):
        w = m.group(0)
        if w not in found:
            found.append(w)
    return found


# ---------- 小工具 ----------
def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_str(v, allow_empty: bool = False) -> bool:
    return isinstance(v, str) and (allow_empty or v.strip() != "")


# ---------- 事件校验 ----------
def validate_event(ev: dict, all_ids: set[str], res: ValidationResult, key: str | None = None) -> None:
    where = f"event {key or ev.get('id', '?')}"
    if not isinstance(ev, dict):
        res.error(where, "事件必须是 JSON 对象")
        return
    for k in EVENT_REQUIRED:
        if k not in ev:
            res.error(where, f"缺少必填字段 {k}")
    for k in ev:
        if k not in EVENT_REQUIRED and k not in EVENT_OPTIONAL:
            res.error(where, f"未知字段 {k}（fail-closed）")
    eid = ev.get("id")
    if not (_is_str(eid) and _EVENT_ID.match(eid)):
        res.error(where, f"id 必须形如 E001，得到 {eid!r}")
    if key is not None and eid != key:
        res.error(where, f"id {eid!r} 与文件名/键 {key!r} 不一致")
    if not _is_str(ev.get("title")):
        res.error(where, "title 必须是非空字符串")
    band, room, kind, inten = ev.get("band"), ev.get("room"), ev.get("kind"), ev.get("intensity")
    if band not in C.BANDS:
        res.error(where, f"band {band!r} 不在允许列表 {list(C.BANDS)}")
    if room not in C.ROOMS:
        res.error(where, f"room {room!r} 不在允许列表 {list(C.ROOMS)}")
    if kind not in C.KINDS:
        res.error(where, f"kind {kind!r} 不在允许列表 {list(C.KINDS)}")
    if inten not in C.INTENSITIES:
        res.error(where, f"intensity {inten!r} 不在允许列表 {list(C.INTENSITIES)}")
    # kind/room/band 一致性
    if kind == "rest" and room != "rest":
        res.error(where, "kind=rest 必须 room=rest")
    if room == "rest" and kind != "rest":
        res.error(where, "room=rest 必须 kind=rest")
    if kind == "ending" and (room != "ending" or band != "end"):
        res.error(where, "kind=ending 必须 room=ending 且 band=end")
    if (room == "ending" or band == "end") and kind != "ending":
        res.error(where, "room=ending / band=end 只允许 kind=ending")
    if kind == "boss" and room != "boss":
        res.error(where, "kind=boss 必须 room=boss")
    if room == "boss" and kind != "boss":
        res.error(where, "room=boss 必须 kind=boss")
    if kind in ("rest", "ending") and inten != "none":
        res.error(where, f"kind={kind} 的 intensity 必须为 none（安全区/结局必须能停）")
    if not _is_str(ev.get("species")):
        res.error(where, "species 必须是非空字符串（无种族写「无」）")
    if not _is_str(ev.get("trigger")):
        res.error(where, "trigger 必须是非空字符串")
    if not _is_str(ev.get("seed")):
        res.error(where, "seed 必须是非空字符串")
    if "note" in ev and not isinstance(ev["note"], str):
        res.error(where, "note 必须是字符串")
    if "free_input" in ev and ev["free_input"] is not False:
        res.error(where, "free_input 首批只允许 false")

    # checks
    checks = ev.get("checks")
    check_attrs: set[str] = set()
    if not isinstance(checks, list):
        res.error(where, "checks 必须是列表（可为空 []）")
    else:
        for a in checks:
            if a not in C.ATTRS:
                res.error(where, f"checks 含非法属性 {a!r}（只允许 str/dex/int）")
            elif a in check_attrs:
                res.error(where, f"checks 重复 {a!r}")
            check_attrs.add(a)

    # settlement 列表
    settlements = ev.get("settlement")
    settle_set: set[str] = set()
    if not isinstance(settlements, list) or not settlements:
        res.error(where, "settlement 必须是非空列表")
    else:
        for s in settlements:
            if s not in C.SETTLEMENTS:
                res.error(where, f"settlement {s!r} 不在枚举列表中")
            settle_set.add(s)

    # feedback
    fb = ev.get("feedback")
    cores = parse_feedback(fb) if isinstance(fb, str) else []
    if not _is_str(fb):
        res.error(where, "feedback 必须是非空字符串")
    elif not cores:
        res.error(where, f"feedback {fb!r} 不含任何核心词 {list(C.FEEDBACK_CORE)}")
    if kind in ("rest", "ending") and "清理" not in cores:
        res.error(where, f"kind={kind} 的 feedback 必须含「清理」")
    if band == "entry" and ({"持续", "连击"} & set(cores)):
        res.warn(where, "入口带 feedback 出现 持续/连击（S1：入口只授权 无或试探）")

    # flags
    flags = ev.get("flags", {})
    if flags is not None:
        if not isinstance(flags, dict):
            res.error(where, "flags 必须是 dict")
        else:
            for k, v in flags.items():
                if not (isinstance(k, str) and _FLAG_KEY.match(k)):
                    res.error(where, f"flags key {k!r} 必须是英文标识（小写字母/数字/下划线）")
                if not isinstance(v, str):
                    res.error(where, f"flags[{k}] 必须是字符串说明")

    # variants
    variants = ev.get("variants")
    if variants is not None:
        if not isinstance(variants, list):
            res.error(where, "variants 必须是字符串列表")
        else:
            for i, v in enumerate(variants):
                if not _is_str(v):
                    res.error(where, f"variants[{i}] 必须是非空字符串")
                elif v == ev.get("seed"):
                    res.error(where, f"variants[{i}] 与 seed 相同")
            if len(variants) > 3:
                res.warn(where, f"variants 共 {len(variants) + 1} 版（含基底），超出 S3 建议的 2-3 版")

    # choices
    choices = ev.get("choices")
    if not isinstance(choices, list) or not choices:
        res.error(where, "choices 必须是非空列表")
        return
    if len(choices) > 4:
        res.error(where, f"choices 最多 4 条，得到 {len(choices)}")
    if kind != "ending" and len(choices) < 2:
        res.error(where, "非结局事件 choices 至少 2 条")
    for i, ch in enumerate(choices):
        _validate_choice(ev, ch, i, choices, all_ids, check_attrs, settle_set, res, where)


def _validate_choice(ev, ch, i, choices, all_ids, check_attrs, settle_set, res, where_ev) -> None:
    where = f"{where_ev} choice#{i + 1}"
    kind, band = ev.get("kind"), ev.get("band")
    if not isinstance(ch, dict):
        res.error(where, "choice 必须是 JSON 对象")
        return
    for k in CHOICE_REQUIRED:
        if k not in ch:
            res.error(where, f"缺少必填字段 {k}")
    for k in ch:
        if k not in CHOICE_REQUIRED and k not in CHOICE_OPTIONAL:
            res.error(where, f"未知字段 {k}（fail-closed）")
    if not _is_str(ch.get("label")):
        res.error(where, "label 必须是非空字符串")
    if not _is_str(ch.get("exit")):
        res.error(where, "exit 必须是非空字符串")
    if "note" in ch and not isinstance(ch["note"], str):
        res.error(where, "note 必须是字符串")
    for bkey in ("estop_overrides", "gate_check"):
        if bkey in ch and not isinstance(ch[bkey], bool):
            res.error(where, f"{bkey} 必须是 bool")

    st = ch.get("settlement")
    if st not in C.SETTLEMENTS:
        res.error(where, f"settlement {st!r} 不在枚举列表中")
    elif settle_set and st not in settle_set:
        res.error(where, f"settlement {st!r} 不在事件 settlement 列表 {sorted(settle_set)}")
    if kind == "ending":
        if st not in C.ENDING_BY_SETTLEMENT:
            res.error(where, f"结局事件 choice 的 settlement 必须是 end_escape/end_stay/end_sink，得到 {st!r}")
    elif st in C.ENDING_BY_SETTLEMENT:
        res.error(where, f"非结局事件不得使用 {st}")
    if st in ("yield", "end_sink") and not ch.get("estop_overrides"):
        res.warn(where, f"settlement={st} 未标 estop_overrides（S3 §九：戏内无法拒绝的 yield/sink 应标）")
    elif st == "defeat" and not ch.get("estop_overrides"):
        res.note(where, "玩家主动选择类 defeat 可免 estop（2026-09-04 主 Agent 拍板）")

    # next
    nxt = ch.get("next")
    if kind == "ending":
        if nxt != C.END_TOKEN:
            res.error(where, f"结局事件 choice 的 next 必须是 {C.END_TOKEN!r}")
    else:
        if nxt == C.END_TOKEN:
            res.error(where, "只有 kind=ending 的 choice 才能 next=end")
        elif nxt == C.MAP_RETURN:
            if _PACK_MODE != C.PACK_MODE_MAP:
                res.error(where, "next=map 仅允许 mode=map 的内容包")
        elif not (_is_str(nxt) and nxt in all_ids):
            res.error(where, f"next {nxt!r} 不是已知事件 id")

    # gate_check / next_uncrossed
    if ch.get("gate_check"):
        if kind != "boss":
            res.warn(where, "gate_check 出现在非 boss 事件（首批唯一入口应为 Boss 交身）")
        nu = ch.get("next_uncrossed")
        if not (_is_str(nu) and nu in all_ids):
            res.error(where, f"gate_check 选项必须写 next_uncrossed（未 crossed 时去向），得到 {nu!r}")
    elif "next_uncrossed" in ch:
        res.error(where, "next_uncrossed 只允许出现在 gate_check=true 的选项")

    # require
    require = ch.get("require")
    attr_key = None
    if require is not None:
        if not isinstance(require, dict) or not require:
            res.error(where, "require 必须是非空 dict")
        else:
            attr_keys = [k for k in require if k in C.REQUIRE_ATTR_KEYS]
            if len(attr_keys) > 1:
                res.error(where, f"require 最多一个属性检定键，得到 {attr_keys}")
            for k, v in require.items():
                if k in C.REQUIRE_ATTR_KEYS:
                    attr_key = k
                    if not (_is_int(v) and 1 <= v <= C.ATTR_MAX):
                        res.error(where, f"属性检定 TN 必须是 1..{C.ATTR_MAX} 的整数，得到 {v!r}")
                    else:
                        lo, hi = (C.TN_BOSS_RANGE if kind == "boss"
                                  else C.TN_BAND_RANGE.get(band, (1, C.ATTR_MAX)))
                        if not (lo <= v <= hi):
                            res.warn(where, f"TN {v} 超出层带建议区间 {lo}-{hi}（band={band}, kind={kind}）")
                    if k not in check_attrs:
                        res.error(where, f"属性检定 {k} 未列入事件 checks")
                elif k == "stage_min":
                    if v not in C.MARK_STAGES:
                        res.error(where, f"stage_min {v!r} 不在允许列表 {list(C.MARK_STAGES)}")
                elif k in C.REQUIRE_GATE_KEYS:
                    if not (_is_int(v) and v >= 0):
                        res.error(where, f"{k} 必须是非负整数")
                else:
                    res.error(where, f"require 含未知/未启用键 {k!r}（mo_hua_gte 首批不实现）")

    # fail
    fail = ch.get("fail")
    if attr_key is not None:
        if not isinstance(fail, dict) or not fail:
            res.error(where, "属性检定 choice 必须显式写 fail")
        else:
            _validate_fail(fail, i, choices, all_ids, kind, res, where)
    elif fail is not None:
        res.error(where, "无属性检定的 choice 不得写 fail")

    # effects
    _validate_effects(ch.get("effects"), res, where)


def _validate_fail(fail, i, choices, all_ids, kind, res, where) -> None:
    if "choice" in fail:
        extra = set(fail) - {"choice"}
        if extra:
            res.error(where, f"fail:{{choice}} 不得混写其他键 {sorted(extra)}")
        n = fail["choice"]
        if not (_is_int(n) and 1 <= n <= len(choices)):
            res.error(where, f"fail.choice 必须是 1..{len(choices)} 的序号，得到 {n!r}")
            return
        if n - 1 == i:
            res.error(where, "fail.choice 不能指向自己")
            return
        target = choices[n - 1]
        if isinstance(target, dict):
            treq = target.get("require") or {}
            if any(k in C.REQUIRE_ATTR_KEYS for k in treq):
                res.error(where, f"fail.choice 指向的第 {n} 条也是属性检定（禁止递归）")
            if any(k not in C.REQUIRE_ATTR_KEYS for k in treq):
                res.warn(where, f"fail.choice 指向的第 {n} 条带状态门槛，折叠时门槛不再检查")
        return
    for k in fail:
        if k not in ("next", "settlement", "exit"):
            res.error(where, f"fail 备用格式只允许 next/settlement/exit，得到 {k!r}")
    nxt = fail.get("next")
    if kind == "ending":
        if nxt != C.END_TOKEN:
            res.error(where, "结局事件 fail.next 必须是 end")
    elif nxt == C.MAP_RETURN:
        if _PACK_MODE != C.PACK_MODE_MAP:
            res.error(where, "fail.next=map 仅允许 mode=map 的内容包")
    elif not (_is_str(nxt) and nxt in all_ids):
        res.error(where, f"fail.next {nxt!r} 不是已知事件 id")
    if fail.get("settlement") not in C.SETTLEMENTS:
        res.error(where, f"fail.settlement {fail.get('settlement')!r} 不在枚举列表中")
    if not _is_str(fail.get("exit")):
        res.error(where, "fail.exit 必须是非空字符串")


def _validate_effects(raw, res, where) -> None:
    if raw is None:
        return
    entries = [raw] if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        res.error(where, "effects 必须是 dict 或 dict 列表")
        return
    for j, e in enumerate(entries):
        w = f"{where} effects[{j}]"
        if not isinstance(e, dict) or not e:
            res.error(w, "每条 effect 必须是非空 dict")
            continue
        payload = 0
        for k, v in e.items():
            if k in C.EFFECT_DELTA_KEYS:
                payload += 1
                if not _is_int(v) or v == 0:
                    res.error(w, f"{k} 必须是非零整数 delta，得到 {v!r}")
            elif k in C.EFFECT_STAGE_KEYS:
                payload += 1
                if v is not True:
                    res.error(w, f"{k} 只允许 true")
            elif k == "dice_gain":
                payload += 1
                if v is not True:
                    res.error(w, "dice_gain 只允许 true")
            elif k == "ability_up":
                payload += 1
                res.warn(w, "ability_up 首批忽略（能力项未实现）")
            elif k == "visit_n_eq":
                if not (_is_int(v) and v >= 1):
                    res.error(w, f"visit_n_eq 必须是 ≥1 的整数，得到 {v!r}")
            else:
                res.error(w, f"未知 effect 键 {k!r}（fail-closed）")
        if payload == 0:
            res.error(w, "effect 条目只有 visit_n_eq、没有任何实际修改")
        stage_keys = [k for k in e if k in C.EFFECT_STAGE_KEYS]
        if len(stage_keys) > 1:
            res.warn(w, f"同一条 effect 含多个 stage 指令 {stage_keys}，按写入顺序覆盖")


# ---------- manifest / theme / bindings ----------
def validate_manifest(m: dict, res: ValidationResult) -> None:
    where = "manifest"
    if not isinstance(m, dict):
        res.error(where, "manifest 必须是 JSON 对象")
        return
    for k in MANIFEST_REQUIRED:
        if k not in m:
            res.error(where, f"缺少必填字段 {k}")
    if m.get("format") != C.PACK_FORMAT:
        res.error(where, f"format 必须是 {C.PACK_FORMAT!r}，得到 {m.get('format')!r}")
    if m.get("format_version") != C.PACK_FORMAT_VERSION:
        res.error(where, f"format_version 必须是 {C.PACK_FORMAT_VERSION}，得到 {m.get('format_version')!r}")
    pid = m.get("id")
    if not (_is_str(pid) and _PACK_ID.match(pid)):
        res.error(where, f"id 必须是小写英文标识，得到 {pid!r}")
    if not _is_str(m.get("title")):
        res.error(where, "title 必须是非空字符串")
    themes = m.get("themes")
    if not (isinstance(themes, list) and themes and all(_is_str(t) for t in themes)):
        res.error(where, "themes 必须是非空字符串列表")
    for k in ("start_event", "safe_room"):
        v = m.get(k)
        if not (_is_str(v) and _EVENT_ID.match(v)):
            res.error(where, f"{k} 必须是事件 id，得到 {v!r}")
    for k in ("events_dir", "theme_file", "bindings_file", "base_setting_file", "version"):
        if not _is_str(m.get(k)):
            res.error(where, f"{k} 必须是非空字符串")



    mode = m.get("mode", C.PACK_MODE_CHAIN)
    if mode not in (C.PACK_MODE_CHAIN, C.PACK_MODE_MAP, None):
        res.error(where, f"mode 必须是 chain/map，得到 {mode!r}")
    elif mode == C.PACK_MODE_MAP:
        res.note(where, "mode=map：包级图校验走 map 分支（池事件可 next=map）")

def validate_theme(t: dict, manifest: dict, res: ValidationResult) -> None:
    where = "theme"
    if not isinstance(t, dict):
        res.error(where, "theme 必须是 JSON 对象")
        return
    for k in ("id", "title", "description", "bands", "feedback_labels"):
        if k not in t:
            res.error(where, f"缺少必填字段 {k}")
    if isinstance(manifest, dict) and t.get("id") != manifest.get("id"):
        res.error(where, f"theme.id {t.get('id')!r} 必须等于 manifest.id {manifest.get('id')!r}")
    bands = t.get("bands")
    if not isinstance(bands, dict) or set(bands) != set(C.BANDS):
        res.error(where, f"bands 必须恰好覆盖 {list(C.BANDS)}")
    fl = t.get("feedback_labels")
    if not isinstance(fl, dict) or set(fl) != set(C.FEEDBACK_CORE):
        res.error(where, f"feedback_labels 必须恰好覆盖 {list(C.FEEDBACK_CORE)}")


def validate_bindings(b: dict, res: ValidationResult, known_patterns: set[str] | None = None) -> None:
    where = "bindings"
    if not isinstance(b, dict):
        res.error(where, "bindings 必须是 JSON 对象")
        return
    for k in BINDINGS_REQUIRED:
        if k not in b:
            res.error(where, f"缺少必填字段 {k}")
    if b.get("format") != "dungeon_v2_bindings":
        res.error(where, "format 必须是 'dungeon_v2_bindings'")
    channels = b.get("channels")
    if not (isinstance(channels, list) and channels and all(c in ("A", "B") for c in channels)):
        res.error(where, "channels 必须是 ['A'] / ['B'] / ['A','B']")
        channels = ["A", "B"]
    bs = b.get("band_strength")
    if not isinstance(bs, dict) or set(bs) != set(C.BANDS):
        res.error(where, f"band_strength 必须恰好覆盖 {list(C.BANDS)}")
    else:
        for k, v in bs.items():
            if not (_is_int(v) and 0 <= v <= 100):
                res.error(where, f"band_strength[{k}] 必须是 0..100 整数")
        if bs.get("end", 0) != 0:
            res.error(where, "band_strength.end 必须为 0（结局结算前清设备）")
    sc = b.get("intensity_scale")
    if not isinstance(sc, dict) or set(sc) != set(C.INTENSITIES):
        res.error(where, f"intensity_scale 必须恰好覆盖 {list(C.INTENSITIES)}")
    else:
        for k, v in sc.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or v > 2:
                res.error(where, f"intensity_scale[{k}] 必须是 0..2 的数")
        if sc.get("none", 1) != 0:
            res.error(where, "intensity_scale.none 必须为 0")
    rhythm = b.get("rhythm")
    if not isinstance(rhythm, dict) or set(rhythm) != set(C.FEEDBACK_CORE):
        res.error(where, f"rhythm 必须恰好覆盖 {list(C.FEEDBACK_CORE)}")
        return
    for core, spec in rhythm.items():
        w = f"{where}.rhythm[{core}]"
        if not isinstance(spec, dict) or "actions" not in spec:
            res.error(w, "必须是 {desc, actions} 对象")
            continue
        if not _is_str(spec.get("desc")):
            res.error(w, "desc 必须是非空字符串（给安全层/审核看的节奏说明）")
        actions = spec.get("actions")
        if not isinstance(actions, list):
            res.error(w, "actions 必须是列表")
            continue
        ops = []
        for j, a in enumerate(actions):
            aw = f"{w}.actions[{j}]"
            if not isinstance(a, dict):
                res.error(aw, "action 必须是对象")
                continue
            op = a.get("op")
            ops.append(op)
            if op not in C.FEEDBACK_ACTION_OPS:
                res.error(aw, f"op {op!r} 不在允许列表 {list(C.FEEDBACK_ACTION_OPS)}（pulse_hold 首批不允许）")
                continue
            if op in ("temp_strength", "hold_strength", "add_strength", "pulse"):
                if a.get("channel") not in channels:
                    res.error(aw, f"channel {a.get('channel')!r} 不在允许列表 {channels}")
            if op in ("temp_strength", "hold_strength"):
                v = a.get("value")
                if not (v == "$strength" or (_is_int(v) and 0 <= v <= 100)):
                    res.error(aw, "value 必须是 '$strength' 或 0..100 整数")
            if op == "add_strength":
                v = a.get("delta")
                if not (_is_int(v) and -40 <= v <= 40):
                    res.error(aw, "delta 必须是 -40..40 整数")
            if op == "pulse":
                p = a.get("pattern")
                if not _is_str(p):
                    res.error(aw, "pattern 必须是非空字符串（波形名单里的中文名）")
                elif known_patterns is not None and p not in known_patterns:
                    res.error(aw, f"pattern {p!r} 不在波形名单")
            if op in ("temp_strength", "pulse") and "duration_s" in a:
                d = a["duration_s"]
                if not isinstance(d, (int, float)) or isinstance(d, bool) or d <= 0 or d > 30:
                    res.error(aw, "duration_s 必须是 0<d<=30 的数")
        if core == "无" and actions:
            res.error(w, "「无」的 actions 必须为空")
        if core == "清理":
            if "clear" not in ops or "stop" not in ops:
                res.error(w, "「清理」必须含 clear + stop（全部清零）")
            if any(o not in ("clear", "stop") for o in ops):
                res.error(w, "「清理」只允许 clear/stop")
        if core == "停顿" and "clear" not in ops:
            res.error(w, "「停顿」必须含 clear")
        if core in ("停顿", "无") and any(o in ("temp_strength", "hold_strength", "add_strength", "pulse") for o in ops):
            res.error(w, f"「{core}」不得输出体感")


# ---------- 包级图校验 ----------
def _edges(events: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {eid: [] for eid in events}
    for eid, ev in events.items():
        for ch in ev.get("choices") or []:
            if not isinstance(ch, dict):
                continue
            for key in ("next", "next_uncrossed"):
                n = ch.get(key)
                if isinstance(n, str) and n in events and n not in out[eid]:
                    out[eid].append(n)
            f = ch.get("fail")
            if isinstance(f, dict) and isinstance(f.get("next"), str) and f["next"] in events:
                if f["next"] not in out[eid]:
                    out[eid].append(f["next"])
    return out


def _reachable(start: str, edges: dict[str, list[str]]) -> set[str]:
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n in seen or n not in edges:
            continue
        seen.add(n)
        stack.extend(edges[n])
    return seen


def validate_pack_graph(events: dict, manifest: dict, res: ValidationResult) -> None:
    where = "pack"
    if not events:
        res.error(where, "没有任何事件")
        return
    start = manifest.get("start_event") if isinstance(manifest, dict) else None
    safe = manifest.get("safe_room") if isinstance(manifest, dict) else None
    if start not in events:
        res.error(where, f"start_event {start!r} 不存在")
        return
    if events[start].get("band") != "entry":
        res.error(where, f"start_event {start} 必须在 entry 带")
    if safe not in events:
        res.error(where, f"safe_room {safe!r} 不存在")
    elif events[safe].get("kind") != "rest":
        res.error(where, f"safe_room {safe} 必须 kind=rest")

    mode = str(manifest.get("mode") or C.PACK_MODE_CHAIN).lower()
    is_map = mode == C.PACK_MODE_MAP

    edges = _edges(events)
    endings = {eid for eid, ev in events.items() if ev.get("kind") == "ending"}
    if not endings:
        res.error(where, "没有 kind=ending 的结局事件")
    kinds_present = {C.ENDING_BY_SETTLEMENT.get(c.get("settlement"))
                     for e in endings for c in (events[e].get("choices") or []) if isinstance(c, dict)}
    for k in ("escape", "stay", "sink"):
        if k not in kinds_present:
            res.warn(where, f"缺少 {k} 类结局")
    bosses = {eid for eid, ev in events.items() if ev.get("kind") == "boss"}
    if not bosses:
        res.error(where, "没有 kind=boss 事件")

    rev: dict[str, list[str]] = {eid: [] for eid in events}
    for a, outs in edges.items():
        for b in outs:
            rev[b].append(a)

    if is_map:
        for e in endings:
            for pred in rev[e]:
                if pred not in bosses:
                    res.error(where, f"结局 {e} 的前驱 {pred} 不是 boss（Boss 必进一次）")
        rooms_covered = {ev.get("room") for ev in events.values() if ev.get("kind") != "ending"}
        for need in ("encounter", "rest", "treasure", "trap", "boss"):
            if need not in rooms_covered:
                res.warn(where, f"map 池缺少 room={need} 事件")
        res.note(where, "mode=map：已豁免链式可达/死胡同全图检查")
        return

    reach = _reachable(start, edges)
    for eid in events:
        if eid not in reach:
            res.error(where, f"事件 {eid} 从 {start} 不可达（孤立节点）")
    can_end: set[str] = set()
    stack = list(endings)
    while stack:
        n = stack.pop()
        if n in can_end:
            continue
        can_end.add(n)
        stack.extend(rev[n])
    for eid in events:
        if eid not in can_end:
            res.error(where, f"事件 {eid} 无法到达任何结局（死循环/死胡同）")
    for e in endings:
        for pred in rev[e]:
            if pred not in bosses:
                res.error(where, f"结局 {e} 的前驱 {pred} 不是 boss（Boss 必进一次）")
    if not any(c.get("gate_check") for b in bosses for c in (events[b].get("choices") or []) if isinstance(c, dict)):
        res.warn(where, "没有任何 gate_check 选项，crossed_gate 永不判定")
    for a in events:
        sa = events[a].get("species")
        if not sa or sa == C.SPECIES_NONE:
            continue
        for b in edges[a]:
            if b == a or events[b].get("species") != sa:
                continue
            for c in edges[b]:
                if c == b or c == a:
                    continue
                if events[c].get("species") == sa:
                    res.error(where, f"连续三场同 species {sa!r}：{a}→{b}→{c}")


# ---------- 总入口 ----------
def validate_tree(tree: dict, known_patterns: set[str] | None = None) -> ValidationResult:
    global _PACK_MODE
    res = ValidationResult()
    manifest = tree.get("manifest")
    events = tree.get("events")
    mode = C.PACK_MODE_CHAIN
    if isinstance(manifest, dict):
        mode = str(manifest.get("mode") or C.PACK_MODE_CHAIN).lower()
        if mode != C.PACK_MODE_MAP:
            mode = C.PACK_MODE_CHAIN
    _PACK_MODE = mode
    try:
        validate_manifest(manifest, res)
        if not isinstance(events, dict):
            res.error("pack", "events 必须是 {id: event} 映射")
            return res
        all_ids = set(events)
        for key, ev in events.items():
            validate_event(ev, all_ids, res, key=key)
        if isinstance(manifest, dict):
            validate_pack_graph(events, manifest, res)
        validate_theme(tree.get("theme"), manifest if isinstance(manifest, dict) else {}, res)
        validate_bindings(tree.get("bindings"), res, known_patterns)
        bs = tree.get("base_setting")
        if not _is_str(bs):
            res.error("base_setting", "base_setting 必须是非空文本")
        return res
    finally:
        _PACK_MODE = C.PACK_MODE_CHAIN
