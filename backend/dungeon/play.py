# -*- coding: utf-8 -*-
"""地牢交互试玩（dry_run）：在命令行里走一遍当前 content/pack 的主题包。

默认不联网（叙事用作者 seed，能离线跑通）；加 `--llm` 则用 config.yaml 的真实 LLM 生成叙事。
加 `--auto` 则自动沿主线选项通关（每次取第一选项，不等待输入）。

运行（仓库根目录）：
  python -m backend.dungeon.play            # 交互式
  python -m backend.dungeon.play --auto     # 自动通关
  python -m backend.dungeon.play --llm      # 真实 AI 叙事（需 config.yaml 配好 API Key）
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ..config import load_config
from ..llm import LLM
from ..safety import SafetyManager
from .feedback import resolve_feedback
from .narrative import NarrativeWriter
from .runtime import DungeonRuntime


def _make_llm(use_llm: bool):
    if not use_llm:
        return None
    try:
        cfg = load_config()
        if not (cfg["llm"].get("api_key") or "").strip():
            print("⚠ 未配置 API Key，改用作者 seed 叙事\n")
            return None
        return LLM(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠ 加载 LLM 失败（{exc}），改用作者 seed 叙事\n")
        return None


async def _print_event(eng, run, pack, writer, ev) -> None:
    fb = resolve_feedback(ev, pack.binding_index)
    rs = run["run_state"]
    print()
    print(f"[第 {run['floor_index']} 层 · 第 {run['room_index']} 房]  {ev['title']}"
          f"  （{ev.get('kind')} · 分级 {ev.get('content_level')} · tier {ev.get('tier')}）")
    print(f"HP {rs['hp']} · 意志 {rs['will']} · 亲和 {rs['affinity']} · 体感[{fb['hint']}]")
    n = await writer.narrate(ev)
    src = "AI" if n["source"] == "llm" else "seed"
    print(f"\n  {n['text']}\n  —（叙事来源：{src}）")
    if run["phase"] == "ending":
        print(f"\n  ==== 结局：{run['ending_id']} ====")


async def _run(use_llm: bool, auto: bool) -> None:
    project_root = Path(__file__).resolve().parents[2]  # AI-for-Coyote
    cfg = load_config()
    safety = SafetyManager(cfg)
    runtime = DungeonRuntime(cfg, _make_llm(use_llm), safety, project_root)

    if not runtime.packs:
        print("没有可用的主题包（content/pack/dungeon/ 下没有 kind: theme_pack）")
        return
    first_id = next(iter(runtime.packs))
    pack = runtime.packs[first_id]
    eng = runtime.engine
    writer = runtime.writer

    print("=" * 62)
    print(f"  紫金地牢 · 试玩（dry_run · 主题：{first_id}）")
    print("  交互式：输入选项编号推进；其他文字=自由输入；q=退出")
    if auto:
        print("  自动通关模式：沿主线选项自动推进（每步取第一选项）")
    print("=" * 62)

    await runtime.start(
        active_themes=list(pack.theme_ids), mix_policy="mixed_pool", floors=3, seed=42
    )

    while True:
        ev = eng.current_event(runtime.run)
        await _print_event(eng, runtime.run, pack, writer, ev)
        if runtime.run["phase"] == "ending":
            break
        choices = ev.get("choices") or []
        if choices:
            print("\n选项：")
            for i, c in enumerate(choices, 1):
                print(f"  {i}. {c['label']}")
        if auto:
            if choices:
                await runtime.advance(choice_id=choices[0]["id"])
            else:
                break
            continue
        print()
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if line.lower() in ("q", "quit", "exit"):
            break
        if line.isdigit() and choices:
            idx = int(line) - 1
            if 0 <= idx < len(choices):
                await runtime.advance(choice_id=choices[idx]["id"])
                continue
            print("  ! 没有这个编号")
            continue
        if line:
            try:
                await runtime.advance(intent_text=line)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {exc}")
        else:
            print("  ! 请选择选项编号，或输入文字")
    print("\n试玩结束。")


def main() -> None:
    ap = argparse.ArgumentParser(description="地牢 dry_run 交互试玩")
    ap.add_argument("--llm", action="store_true", help="用 config.yaml 的真实 LLM 生成叙事")
    ap.add_argument("--auto", action="store_true", help="自动沿主线选项通关（每次取第一选项）")
    args = ap.parse_args()
    asyncio.run(_run(args.llm, args.auto))


if __name__ == "__main__":
    main()
