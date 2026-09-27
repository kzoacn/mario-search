"""Replay every published route in fresh processes without running a search."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("runs/archive-verification"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def check(route):
        target = output / route.stem
        command = [sys.executable, "-m", "mario_search", "replay", "--route", str(route),
                   "--output", str(target), "--verify-only"]
        process = subprocess.run(command, text=True, capture_output=True, timeout=120)
        if process.returncode:
            raise RuntimeError(f"{route.stem}: {process.stderr}")
        proof = json.loads((target / "replay-verification.json").read_text())
        return {"level": route.stem, "verified": proof["verified"], "success": proof["success"],
                "decisions": proof["decisions"]}

    routes = sorted((root / "benchmarks/routes").glob("*.json"))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(check, routes))
    result = {"verified": sum(r["verified"] for r in rows), "levels": len(rows),
              "successes": sum(r["success"] for r in rows), "results": rows}
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
