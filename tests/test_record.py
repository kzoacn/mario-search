import json
from pathlib import Path

from mario_search.record import replay


def test_archived_success_and_partial_routes_replay_without_search(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for level, success in [("1-1", True), ("4-4", False)]:
        proof = replay(root / "benchmarks/routes" / f"{level}.json", tmp_path / level, video=False)
        assert proof["verified"] and proof["success"] == success
        assert proof["final"]["flag_get"] == success
        assert json.loads((tmp_path / level / "replay-verification.json").read_text())["verified"]
