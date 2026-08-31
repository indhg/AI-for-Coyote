# -*- coding: utf-8 -*-
"""配置加载：config/config.yaml（主配置）+ config/waveforms.yaml（波形与波形库）。

所有「可能要细调」的参数都集中在 config/ 目录的 YAML 里，改完重启生效：
- config.yaml：模型、安全上限、页面快捷按钮
- waveforms.yaml：播放参数、波形库（中文名 -> 波形 + 默认/最长时长）、自定义波形
- character.yaml：角色设定
"""
import copy
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

from . import waveforms as wf_mod

# 打包（PyInstaller）后以 exe 所在目录为项目根；开发时以仓库根
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
logger = logging.getLogger("ai-for-coyote.config")

DEFAULTS = {
    "app": {
        "host": "127.0.0.1",
        "port": 8000,
        "dry_run": True,
        "title": "Coyote in Cradle",
        "sensor_idle_timeout_s": 30,
        "check_update": True,
    },
    "relay": {"url": "ws://127.0.0.1:9998", "reconnect_delay_s": 3, "lan_ip": "auto", "public_url": ""},
    "llm": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
        "temperature": 1.0,
        "max_tokens": 1500,
        "timeout_s": 60,
        "json_mode": True,
        "vision": {
            "base_url": "",
            "api_key": "",
            "model": "",
        },
    },
    "character_file": "config/character.yaml",
    "safety": {
        "channels": {"A": {"max_strength": 200}, "B": {"max_strength": 200}},
        "max_temp_duration_s": 10,
        "max_strength_step": 40,
        "auto_clear_on_disconnect": True,
        "overheat_reduce_to": 20,
    },
    "playback": {
        "frame_ms": 100,
        "min_duration_s": 3,
        "max_duration_s": 10,
        "loop_batch_s": 30,
        "loop_overlap_s": 0.3,
    },
    "ui": {
        "quick_strengths": [20, 40, 60, 80],
        "baseline_strength": {"A": 15, "B": 5},
        "default_wave": "呼吸",
        "default_temp_s": 3,
        "default_pulse_s": 5,
    },
    "presets": {},
    "waveform_data": {},
    "camera": {
        "enabled": False,
        "index": 0,
        "interval_s": 1.5,
        "auto_observe": True,
        "observe_interval_s": 10,
        "dark_threshold": 20.0,
    },
    "audio": {
        "enabled": False,
        "interval_s": 4.0,
        "threshold": 0.005,
        "min_segment_s": 0.8,
        "model_size": "small",
        "language": "zh",
        # 呻吟分级：片段电平 >= threshold*moan_high_multiple 算高声呻吟/惨叫
        "moan_high_multiple": 4.0,
        "moan_cooldown_s": 5.0,
        "silence_timeout_s": 90.0,
    },
    "log": {"dir": "logs", "level": "INFO", "history_keep": 40},
    # 自动运行（AI 自主观察/调整/发言，玩家不用打字；页面底部开关控制）
    "autopilot": {"enabled": False, "interval_s": 12},
    # A/B 通道接的配件（台词描写位置与设备一致用；UI 可改，存 config/device_channels.yaml）
    # baseline = 该配件的强度基准（敏感配件低：贴片15、肛塞5）
    "device_channels": {
        "A": {"name": "贴片", "location": "小穴", "baseline": 15},
        "B": {"name": "肛塞", "location": "后穴", "baseline": 5},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config(dict):
    """支持属性访问的配置字典。"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path else CONFIG_DIR / "config.yaml"
    if not path.exists():
        # 新 clone 的仓库没有 config.yaml（含密钥，不入库）时，回退到示例配置
        fallback = CONFIG_DIR / "config.example.yaml"
        logger.warning("未找到 %s，使用示例配置 %s（请复制为 config.yaml 并填入密钥）", path, fallback)
        path = fallback
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = Config(_deep_merge(DEFAULTS, raw))

    # dry_run 可用环境变量覆盖（联调用）：DGLAB_DRY_RUN=false
    env_dry = os.environ.get("DGLAB_DRY_RUN", "").strip().lower()
    if env_dry in ("0", "false", "no"):
        cfg["app"]["dry_run"] = False
    elif env_dry in ("1", "true", "yes"):
        cfg["app"]["dry_run"] = True

    # 密钥优先级：环境变量 > 配置文件
    env_key = os.environ.get("DGLAB_LLM_API_KEY", "").strip()
    if env_key:
        cfg["llm"]["api_key"] = env_key

    # 示例配置里的中文占位密钥一律按未配置处理（否则会作为 Authorization 头导致编码崩溃、无文字输出）
    for sec in ("llm", "vision"):
        section = cfg.setdefault(sec, {})
        k = str(section.get("api_key") or "")
        try:
            k.encode("ascii")
        except UnicodeEncodeError:
            logger.warning("检测到 %s.api_key 含非 ASCII 字符（疑似示例占位符），已按未配置处理", sec)
            section["api_key"] = ""

    # 角色设定（每次读取最新内容，改完即生效）
    char_path = PROJECT_ROOT / cfg["character_file"]
    if not char_path.exists():
        fallback = CONFIG_DIR / "character.example.yaml"
        logger.warning("未找到 %s，使用示例角色设定 %s", char_path, fallback)
        char_path = fallback
    cfg["character"] = _load_character(char_path)
    cfg["character_file"] = str(char_path)

    # 安全参数数值化校验
    for ch in ("A", "B"):
        cap = int(cfg["safety"]["channels"][ch]["max_strength"])
        cfg["safety"]["channels"][ch]["max_strength"] = max(0, min(200, cap))
    cfg["safety"]["max_temp_duration_s"] = max(
        1, int(cfg["safety"]["max_temp_duration_s"])
    )

    # 波形与波形库（config/waveforms.yaml）
    _load_waveforms(cfg)

    # 通道配件（config/device_channels.yaml，UI 可改后落盘）
    cfg["device_channels"] = _load_device_channels()

    # 日志目录
    log_dir = PROJECT_ROOT / cfg["log"]["dir"]
    log_dir.mkdir(parents=True, exist_ok=True)
    cfg["log_dir"] = str(log_dir)

    return cfg


DEVICE_CHANNELS_FILE = CONFIG_DIR / "device_channels.yaml"


def _load_device_channels() -> dict:
    """读取通道配件配置；文件不存在/缺项时用默认值（A=贴片·大腿根内侧，B=肛塞·后穴）。"""
    base = copy.deepcopy(DEFAULTS["device_channels"])
    raw = {}
    if DEVICE_CHANNELS_FILE.exists():
        try:
            raw = yaml.safe_load(DEVICE_CHANNELS_FILE.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("device_channels.yaml 读取失败，用默认值: %s", exc)
    if isinstance(raw, dict):
        for ch in ("A", "B"):
            entry = raw.get(ch)
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                location = str(entry.get("location") or "").strip()
                if name:
                    base[ch]["name"] = name
                    base[ch]["location"] = location
                if "enabled" in entry:
                    base[ch]["enabled"] = bool(entry["enabled"])
                if "baseline" in entry:
                    try:
                        base[ch]["baseline"] = int(entry["baseline"])
                    except (TypeError, ValueError):
                        pass
    return base


def save_device_channels(cfg: Config, data: dict) -> None:
    """校验并保存通道配件（UI 调用）。data: {A:{name,location[,enabled][,baseline]}, B:{...}}。"""
    if not isinstance(data, dict):
        raise ValueError("参数必须是 JSON 对象")
    clean = {"A": dict(cfg["device_channels"].get("A", {})),
             "B": dict(cfg["device_channels"].get("B", {}))}
    for ch in ("A", "B"):
        entry = data.get(ch)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"{ch} 通道参数必须是对象")
        if "enabled" in entry:
            clean[ch]["enabled"] = bool(entry["enabled"])
        name = str(entry.get("name") or "").strip()
        location = str(entry.get("location") or "").strip()
        if name:
            clean[ch]["name"] = name
            clean[ch]["location"] = location
        if "baseline" in entry:
            try:
                clean[ch]["baseline"] = max(0, min(100, int(entry["baseline"])))
            except (TypeError, ValueError):
                raise ValueError(f"{ch} 通道基准强度必须是数字")
    cfg["device_channels"] = clean
    DEVICE_CHANNELS_FILE.write_text(
        yaml.safe_dump(clean, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("通道配件已保存：A=%s B=%s", clean["A"], clean["B"])


def _load_waveforms(cfg: Config) -> None:
    """加载 waveforms.yaml：播放参数 + 波形库 + 自定义波形。"""
    wf_path = CONFIG_DIR / "waveforms.yaml"
    raw = {}
    if wf_path.exists():
        raw = yaml.safe_load(wf_path.read_text(encoding="utf-8")) or {}

    cfg["playback"] = _deep_merge(DEFAULTS["playback"], raw.get("playback") or {})
    playback = cfg["playback"]
    playback["frame_ms"] = max(1, int(playback["frame_ms"]))
    playback["min_duration_s"] = max(1.0, float(playback["min_duration_s"]))
    playback["max_duration_s"] = max(
        playback["min_duration_s"], float(playback["max_duration_s"])
    )
    playback["loop_batch_s"] = max(2.0, float(playback["loop_batch_s"]))
    playback["loop_overlap_s"] = max(0.0, float(playback["loop_overlap_s"]))

    # 合并自定义波形到内置波形数据
    merged = copy.deepcopy(wf_mod.WAVEFORMS)
    for key, entry in (raw.get("custom") or {}).items():
        if not isinstance(entry, dict):
            continue
        frames = [str(f) for f in entry.get("frames") or []]
        if not frames:
            logger.warning("自定义波形 %s 没有帧数据，已忽略", key)
            continue
        merged[str(key)] = {
            "cn": str(entry.get("label", key)),
            "en": str(key),
            "frames": frames,
        }
    cfg["waveform_data"] = merged

    # 波形库：中文名 -> {waveform, frames, default_duration_s, max_duration_s}
    presets: dict = {}
    max_dur = playback["max_duration_s"]
    default_pulse = float(cfg["ui"]["default_pulse_s"])
    for name, meta in (raw.get("presets") or {}).items():
        if isinstance(meta, str):
            meta = {"waveform": meta}
        if not isinstance(meta, dict):
            continue
        key = str(meta.get("waveform", ""))
        data = merged.get(key)
        if not data:
            logger.warning("波形 %s 引用的波形 %s 不存在，已跳过", name, key)
            continue
        try:
            move_max = float(meta.get("max_duration_s", max_dur))
        except (TypeError, ValueError):
            move_max = max_dur
        try:
            move_default = float(meta.get("default_duration_s", default_pulse))
        except (TypeError, ValueError):
            move_default = default_pulse
        presets[str(name)] = {
            "waveform": key,
            "label": data["cn"],
            "frames": data["frames"],
            "default_duration_s": min(move_default, move_max),
            "max_duration_s": min(move_max, max_dur),
            "category": str(meta.get("category", "经典波形")),
        }
    cfg["presets"] = presets
    logger.info(
        "波形库加载：%d 个波形（自定义波形 %d 个）",
        len(presets), len(merged) - len(wf_mod.WAVEFORMS),
    )


def reload_character(cfg: Config) -> None:
    """热加载角色设定：调教时改完 character.yaml，下一条消息即生效。"""
    cfg["character"] = _load_character(Path(cfg["character_file"]))


# 角色运行时覆盖（页面切换风格版本/改昵称后落盘，重启后仍生效）
CHARACTER_RUNTIME_FILE = CONFIG_DIR / "character_runtime.yaml"


def _load_character_runtime() -> dict:
    if CHARACTER_RUNTIME_FILE.exists():
        try:
            raw = yaml.safe_load(CHARACTER_RUNTIME_FILE.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                return raw
        except Exception as exc:  # noqa: BLE001
            logger.warning("character_runtime.yaml 读取失败，忽略: %s", exc)
    return {}


def _parse_examples(data: dict | None) -> list:
    examples = []
    for item in data or []:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user", "")).strip()
        assistant = item.get("assistant")
        if isinstance(assistant, dict):
            assistant = {
                "line": str(assistant.get("line", "")).strip(),
                "actions": assistant.get("actions") or [],
            }
        else:
            assistant = str(assistant or "").strip()
        if user and assistant:
            examples.append({"user": user, "assistant": assistant})
    return examples


def _prompt_exists(pf) -> bool:
    if not pf:
        return False
    pp = Path(str(pf))
    if not pp.is_absolute():
        pp = PROJECT_ROOT / pp
    return pp.exists()


def _prompt_read(pf) -> str:
    if not pf:
        return ""
    pp = Path(str(pf))
    if not pp.is_absolute():
        pp = PROJECT_ROOT / pp
    if pp.exists():
        return pp.read_text(encoding="utf-8").strip()
    logger.warning("角色提示词文件不存在: %s", pp)
    return ""


def _load_character(path: Path) -> dict:
    if not path.exists():
        return {
            "name": "默认角色",
            "role": "默认角色",
            "role_title": "主人",
            "device_narrative": "触手",
            "roles": [],
            "prompt": "你是一个有趣的互动角色。",
            "player_nick": "小柳",
            "profile": "默认",
            "profiles": ["默认"],
            "profile_available": {},
            "prompt_file": None,
            "examples": [],
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    runtime = _load_character_runtime()

    # 新格式：roles.<角色>.profiles.<风格>；旧格式（平铺 profiles）包装成单角色「触手」
    roles_raw = data.get("roles")
    if isinstance(roles_raw, dict) and roles_raw:
        role_meta: dict[str, dict] = {}
        for rname, rbody in roles_raw.items():
            if not isinstance(rbody, dict):
                continue
            rprofiles = rbody.get("profiles") if isinstance(rbody.get("profiles"), dict) else {}
            role_meta[rname] = {
                "name": str(rbody.get("name") or rname),
                "title": str(rbody.get("title") or "主人"),
                "device_narrative": str(rbody.get("device_narrative") or "触手"),
                "profiles": rprofiles,
            }
        role_names = list(role_meta)
        role_name = str(runtime.get("role") or data.get("role") or role_names[0]).strip()
        if role_name not in role_meta:
            role_name = role_names[0]
    else:
        role_meta = {
            "触手": {
                "name": str(data.get("name") or "触手"),
                "title": "主人",
                "device_narrative": "触手",
                "profiles": (
                    data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
                ),
            }
        }
        role_name = "触手"

    meta = role_meta[role_name]
    profiles_map = meta["profiles"] or {}
    available_profiles = list(profiles_map) or ["默认"]
    profile_name = str(runtime.get("profile") or data.get("profile") or available_profiles[0]).strip()
    if profile_name not in available_profiles:
        profile_name = available_profiles[0]
    profile = profiles_map.get(profile_name) or {}
    top_prompt_file = data.get("prompt_file")

    # 各角色 × 各风格的可用性清单（前端两级选择用）
    roles_out: list[dict] = []
    for rname, rmeta in role_meta.items():
        profs_out: list[dict] = []
        for pname, pbody in rmeta["profiles"].items():
            pf = pbody.get("prompt_file") or top_prompt_file
            profs_out.append(
                {
                    "name": pname,
                    "level": str(pbody.get("level") or "中"),
                    "note": str(pbody.get("note") or "").strip(),
                    "available": _prompt_exists(pf),
                }
            )
        roles_out.append(
            {
                "name": rname,
                "label": rmeta["name"],
                "title": rmeta["title"],
                "device_narrative": rmeta["device_narrative"],
                "profiles": profs_out,
            }
        )

    current_profs = next((r["profiles"] for r in roles_out if r["name"] == role_name), [])
    profile_available = {p["name"]: p["available"] for p in current_profs}

    prompt_file = profile.get("prompt_file") or top_prompt_file
    prompt = _prompt_read(prompt_file)
    if not prompt:
        prompt = str(data.get("prompt", "")).strip()
        if prompt_file:
            # 文件缺失/为空时视为无外部提示词：build_system_prompt 会改走内置完整 JSON/op 规范
            # （否则输出格式约束丢失，模型可能只回动作不回台词）
            logger.warning("提示词文件缺失，改用内置输出格式规范: %s", prompt_file)
            prompt_file = None

    examples = _parse_examples(
        profile.get("examples") if profile.get("examples") is not None else data.get("examples")
    )

    nick = str(
        runtime.get("player_nick") or data.get("player_nick") or "小柳"
    ).strip() or "小柳"

    sel_level = next((p["level"] for p in current_profs if p["name"] == profile_name), "中")
    return {
        "name": meta["name"],
        "role": role_name,
        "role_title": meta["title"],
        "device_narrative": meta["device_narrative"],
        "roles": roles_out,
        "prompt": prompt,
        "player_nick": nick,
        "profile": profile_name,
        "profiles": [p["name"] for p in current_profs],
        "profile_level": sel_level,
        "profile_note": next((p["note"] for p in current_profs if p["name"] == profile_name), ""),
        # 基准怒气按档位固定（用户定）：纯爱 0 / 调教 1 / 凌辱 2
        "rage_baseline": {"轻": 0, "中": 1, "重": 2}.get(sel_level, 0),
        "profile_available": profile_available,
        "prompt_file": prompt_file,
        "examples": examples,
    }


def save_character_runtime(cfg: Config, **fields) -> None:
    """保存运行时角色覆盖（profile / player_nick）并立即热加载。

    fields 只接受 profile 与 player_nick 两个键；值为 None 的键不写。
    """
    runtime = _load_character_runtime()
    for key, value in fields.items():
        if key not in ("role", "profile", "player_nick"):
            continue
        if value is None:
            continue
        runtime[key] = str(value).strip()
    CHARACTER_RUNTIME_FILE.write_text(
        yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    cfg["character"] = _load_character(Path(cfg["character_file"]))
    logger.info("角色运行时覆盖已保存：%s", runtime)


def patch_character_prompt_file(
    character_path: Path,
    profile: str,
    prompt_rel: str,
    role: str = "",
    level: str | None = None,
) -> bool:
    """把 character.yaml 里指定角色/风格的 prompt_file 设为 prompt_rel（相对项目根的 posix 路径）。

    新格式按 role 定位角色块，旧格式直接找 profile 键；level 给定时一并修正该风格的档位；
    文件不存在时先从 character.example.yaml 复制；找不到对应键返回 False。供「导入 DLC」自动接通使用。
    """
    if not character_path.exists():
        example = character_path.parent / "character.example.yaml"
        if not example.exists():
            return False
        shutil.copy2(example, character_path)

    text = character_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    idx: int | None = None
    indent = 0
    if role:
        # 先定位角色块，再在块内找 profile 键
        role_re = re.compile(r"^(\s*)" + re.escape(role) + r"\s*:")
        r_idx: int | None = None
        role_indent = 0
        for i, ln in enumerate(lines):
            m = role_re.match(ln)
            if m:
                r_idx = i
                role_indent = len(m.group(1))
                break
        if r_idx is None:
            return False
        for j in range(r_idx + 1, len(lines)):
            ln = lines[j]
            if not ln.strip():
                continue
            cur_indent = len(ln) - len(ln.lstrip(" "))
            if cur_indent <= role_indent:
                break
            m = re.match(r"^\s*" + re.escape(profile) + r"\s*:", ln)
            if m:
                idx = j
                indent = cur_indent
                break
        if idx is None:
            return False
    else:
        key_re = re.compile(r"^(\s*)" + re.escape(profile) + r"\s*:")
        for i, ln in enumerate(lines):
            m = key_re.match(ln)
            if m:
                idx = i
                indent = len(m.group(1))
                break
        if idx is None:
            return False

    pline: int | None = None
    lline: int | None = None
    for j in range(idx + 1, len(lines)):
        ln = lines[j]
        if not ln.strip():
            continue
        cur_indent = len(ln) - len(ln.lstrip(" "))
        if cur_indent <= indent:
            break
        if re.match(r"^\s*#?\s*prompt_file\s*:", ln):
            pline = j
        elif level is not None and re.match(r"^\s*#?\s*level\s*:", ln):
            lline = j

    new_line = " " * (indent + 2) + f"prompt_file: {prompt_rel}"
    if pline is not None:
        lines[pline] = new_line
    else:
        lines.insert(idx + 1, new_line)

    if level is not None:
        lv_line = " " * (indent + 2) + f"level: {level}"
        if lline is not None:
            lines[lline] = lv_line
        else:
            lines.insert(idx + 1, lv_line)

    character_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("character.yaml 已更新：%s.%s.prompt_file = %s", role or "-", profile, prompt_rel)
    return True


def patch_character_add_role(
    character_path: Path,
    role: str,
    label: str,
    profile: str,
    level: str,
    prompt_rel: str,
    narrative: str = "装置",
) -> bool:
    """新角色自动注册：在 character.yaml 的 roles 段追加一个角色块（角色已存在则拒绝）。

    供「导入 DLC」傻瓜式接入新角色使用；块插在顶层 prompt: 之前（roles 是它前面的顶层键）。
    """
    if not character_path.exists():
        example = character_path.parent / "character.example.yaml"
        if not example.exists():
            return False
        shutil.copy2(example, character_path)

    text = character_path.read_text(encoding="utf-8")
    if re.search(r"^\s*" + re.escape(role) + r"\s*:\s*$", text, flags=re.M):
        logger.warning("角色 %s 已在 character.yaml 中存在，跳过注册", role)
        return False

    block = [
        f"  {role}:",
        f"    name: {label}",
        "    title: 主人",
        f"    device_narrative: {narrative}",
        "    profiles:",
        f"      {profile}:",
        f"        level: {level}",
        f"        prompt_file: {prompt_rel}",
        "        examples: []",
    ]
    lines = text.splitlines()
    insert_at = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*prompt\s*:", ln):
            insert_at = i
            break
    if insert_at is not None:
        lines[insert_at:insert_at] = block
    else:
        lines += [""] + block
    character_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("character.yaml 已注册新角色：%s（%s·%s）", role, profile, level)
    return True
