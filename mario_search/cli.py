"""CLI for bounded search, independent replay, and parallel level suites."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .io import read_json, sha256, write_json
from .native import SearchEnv
from .record import replay
from .search import BestFirstSearch


class SearchInterrupted(Exception):
    pass


def level_name(value):
    try:
        world, stage = map(int, value.split("-"))
        if not (1 <= world <= 8 and 1 <= stage <= 4):
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("Use a level from 1-1 through 8-4") from None
    return f"{world}-{stage}"


def search(args):
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "search.json").exists():
        raise FileExistsError("Each search must use a fresh output folder")
    world, stage = map(int, args.level.split("-"))
    write_json(folder / "status.json", {"phase": "initializing", "level": args.level, "pid": os.getpid()})
    setup_started = time.monotonic()
    env = SearchEnv(seed=123, horizon=1200, world=world, stage=stage)
    planner = BestFirstSearch(env, seed=123, macro=4, max_nodes=args.max_nodes)
    _, initial = env.reset()
    started, started_at = time.monotonic(), time.time()
    setup_seconds = started - setup_started
    last_report = [0.]
    stop_reason = ["deadline"]
    old_handlers = {}

    def stop(_signum, _frame):
        stop_reason[0] = "user_stop"
        raise SearchInterrupted

    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, stop)
    original_advance = env.env.unwrapped._frame_advance

    def bounded_advance(action):
        if time.monotonic() - started >= args.seconds - 1.:
            raise SearchInterrupted
        return original_advance(action)

    env.env.unwrapped._frame_advance = bounded_advance

    def progress(current):
        elapsed = time.monotonic() - started
        if elapsed - last_report[0] < 2:
            return
        last_report[0] = elapsed
        row = {"phase": "searching", "level": args.level, "elapsed_seconds": elapsed,
               "budget_seconds": args.seconds, "search_actions": current.actions,
               "expanded": current.expanded, "created_nodes": current.created_nodes,
               "furthest_x": current.furthest, "best_surviving_x": current.best_x,
               "pid": os.getpid(), "started_at": started_at}
        write_json(folder / "status.json", row)
        write_json(folder / "last-safe-prefix.json", {**row, "actions": current.best_prefix,
                                                       "route_info": current.best_info})
        with (folder / "progress.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        print(f"{args.level}  {elapsed:6.1f}/{args.seconds:g}s  "
              f"actions={current.actions}  nodes={current.created_nodes}  x={current.furthest}", flush=True)

    try:
        try:
            result = planner.search(lambda: time.monotonic() - started < args.seconds - 1., progress)
        except SearchInterrupted:
            result = {"success": False, "actions": planner.best_prefix,
                      "decisions": len(planner.best_prefix), "search_actions": planner.actions,
                      "expanded": planner.expanded, "created_nodes": planner.created_nodes,
                      "furthest_x": planner.furthest, "controlled_frames": planner.frames,
                      "best_surviving_x": planner.best_x,
                      "route_info": getattr(planner, "best_info", initial), "reason": stop_reason[0]}
        elapsed = time.monotonic() - started
        result.update(level=args.level, world=world, stage=stage, initial=initial,
                      search_wall_seconds=elapsed, budget_seconds=args.seconds,
                      within_budget=elapsed <= args.seconds, setup_seconds=setup_seconds,
                      started_at=started_at, completed_at=time.time(), max_nodes=args.max_nodes,
                      macro=4, repeat=4, horizon=1200, candidates=[3, 4, 2, 1, 0],
                      algorithm="best-first: x - 0.1 * path decisions",
                      versions={name: importlib.metadata.version(name) for name in
                                ["numpy", "nes-py", "gym", "gym-super-mario-bros"]})
        from gym_super_mario_bros._roms import rom_path
        result["rom_sha256"] = sha256(rom_path(lost_levels=False, rom_mode="vanilla"))
        result["source_sha256"] = {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")}
        if not result["within_budget"]:
            result["success"] = False
            result["reason"] = "deadline_overrun"
            safe_path = folder / "last-safe-prefix.json"
            safe = read_json(safe_path) if safe_path.exists() else {"actions": [], "route_info": initial}
            result["actions"], result["route_info"] = safe["actions"], safe["route_info"]
            result["decisions"] = len(result["actions"])
        write_json(folder / "search.json", result)
        write_json(folder / "status.json", {k: v for k, v in {**result, "phase": "searched"}.items() if k != "actions"})
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        env.close()
    if args.video:
        # Fresh interpreter = original installed nes-py, without the search library.
        subprocess.run([sys.executable, "-m", "mario_search", "replay", "--route", str(folder / "search.json"),
                        "--output", str(folder)], check=True, timeout=180)
    print(json.dumps({k: v for k, v in result.items() if k not in ["actions", "source_sha256"]}), flush=True)
    return result


def gallery(folder, results):
    cards = []
    for result in results:
        level = result["level"]
        verdict = "CLEARED" if result.get("success") else "NOT CLEARED"
        video = folder / level / "route.mp4"
        media = f'<video controls preload="none" src="{level}/route.mp4"></video>' if video.exists() else ""
        cards.append(f'<article><h2>{level} · {verdict}</h2>{media}'
                     f'<p>{result.get("search_wall_seconds", 0):.2f}s · {html.escape(result.get("reason", "error"))}</p></article>')
    page = '<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mario search</title><style>body{background:#101820;color:#e8eef3;font:16px system-ui;margin:30px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{background:#182736;padding:18px;border-radius:12px}video{width:100%}</style><h1>Mario save-state search</h1><main>' + "".join(cards) + "</main></html>"
    (folder / "index.html").write_text(page)


def benchmark(args):
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "manifest.json").exists():
        raise FileExistsError("Use a fresh benchmark folder")
    levels = args.levels or [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)]
    write_json(folder / "manifest.json", {"levels": levels, "seconds": args.seconds,
                                         "max_nodes": args.max_nodes, "jobs": args.jobs})

    def job(level):
        target = folder / level
        target.mkdir()
        cmd = [sys.executable, "-m", "mario_search", "search", "--level", level,
               "--seconds", str(args.seconds), "--max-nodes", str(args.max_nodes), "--output", str(target)]
        if args.video:
            cmd.append("--video")
        try:
            with (target / "run.log").open("w") as log:
                subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True,
                               timeout=args.seconds + (210 if args.video else 30))
            return read_json(target / "search.json")
        except (subprocess.SubprocessError, OSError) as exc:
            return {"level": level, "success": False, "reason": "worker_error", "error": str(exc)}

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed([pool.submit(job, level) for level in levels]):
            results.append(future.result())
            write_json(folder / "status.json", {"completed": len(results), "total": len(levels),
                                                "successes": sum(r.get("success", False) for r in results)})
            print(f"Completed {len(results)}/{len(levels)}", flush=True)
    results.sort(key=lambda r: tuple(map(int, r["level"].split("-"))))
    write_json(folder / "summary.json", {"levels": len(levels), "successes": sum(r.get("success", False) for r in results), "results": results})
    gallery(folder, results)
    if any(r.get("reason") == "worker_error" for r in results):
        raise RuntimeError("Some workers failed; inspect summary.json and their run.log files")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("search", "benchmark"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--seconds", type=float, default=300)
        command.add_argument("--max-nodes", type=int, default=6000)
        command.add_argument("--video", action="store_true")
        if name == "search":
            command.add_argument("--level", type=level_name, default="1-1")
        else:
            command.add_argument("--levels", type=level_name, nargs="+")
            command.add_argument("--jobs", type=int, default=4)
    command = sub.add_parser("replay")
    command.add_argument("--route", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.mode != "replay" and (not 1 < args.seconds <= 900 or args.max_nodes <= 0):
        parser.error("seconds must be in (1,900] and max-nodes must be positive")
    if args.mode == "benchmark" and args.jobs <= 0:
        parser.error("jobs must be positive")
    if args.mode == "benchmark" and args.levels and len(set(args.levels)) != len(args.levels):
        parser.error("levels must not contain duplicates")
    needs_video = (args.mode == "replay" and not args.verify_only) or (args.mode != "replay" and args.video)
    if needs_video and not shutil.which("ffmpeg"):
        parser.error("MP4 recording requires ffmpeg on PATH")
    if args.mode == "search":
        search(args)
    elif args.mode == "benchmark":
        benchmark(args)
    else:
        print(json.dumps(replay(args.route, args.output, video=not args.verify_only)), flush=True)


if __name__ == "__main__":
    main()
