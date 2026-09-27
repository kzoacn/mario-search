"""Verify saved actions in an ordinary emulator, optionally encoding an MP4."""
from pathlib import Path
import shutil
import subprocess

from .environment import Monitor, ReferenceEnv
from .io import read_json, sha256, write_json


class VideoMonitor(Monitor):
    def __init__(self, path):
        super().__init__()
        if path.exists():
            raise FileExistsError(f"Video already exists; use a fresh output folder: {path}")
        if not shutil.which("ffmpeg"):
            raise RuntimeError("MP4 recording requires ffmpeg on PATH")
        self.last = None
        self.video_frames = 0
        self.log = path.with_suffix(".ffmpeg.log").open("wb")
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "256x240", "-r", "60", "-i", "-",
            "-an", "-vf", "scale=768:720:flags=neighbor", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-threads", "1", "-movflags", "+faststart", str(path),
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.log)

    def record(self, frame):
        super().record(frame)
        self.last = frame.copy()
        self.process.stdin.write(self.last.tobytes())
        self.video_frames += 1

    def close(self):
        if self.last is not None:
            for _ in range(120):
                self.process.stdin.write(self.last.tobytes())
        self.process.stdin.close()
        result = self.process.wait(timeout=45)
        self.log.close()
        if result:
            raise RuntimeError(f"ffmpeg exited with code {result}")


def replay(route_path, output, *, video=True):
    route_path, output = Path(route_path), Path(output)
    result = read_json(route_path)
    output.mkdir(parents=True, exist_ok=True)
    proof_path = output / "replay-verification.json"
    if proof_path.exists():
        raise FileExistsError(f"Replay already exists: {proof_path}")
    level = result["level"]
    world, stage = map(int, level.split("-"))
    env = ReferenceEnv(seed=123, horizon=result.get("horizon", 1200), world=world, stage=stage)
    recorder = None
    try:
        _, initial = env.reset()
        if initial != result["initial"]:
            raise AssertionError("The reference entrance differs from the recorded entrance")
        if video:
            recorder = VideoMonitor(output / "route.mp4")
            env.monitor = recorder
            env.env.env.monitor = recorder
            recorder.record(env.env.unwrapped.screen)
        info = initial
        frames = 0
        total_reward = 0.
        done = False
        for index, action in enumerate(result["actions"]):
            _, row = env.step(action)
            info, done = row["info"], row["done"]
            frames += row["controlled_frames"]
            total_reward += row["reward"]
            if done and index != len(result["actions"]) - 1:
                raise AssertionError("The replay ended before the saved route")
        if info != result["route_info"] or bool(info["flag_get"]) != result["success"]:
            raise AssertionError("The replay's final native state differs from the search result")
        if result["success"] and not done:
            raise AssertionError("A successful replay must terminate at the native goal")
    finally:
        if recorder:
            recorder.close()
        env.close()
    proof = {"verified": True, "level": level, "success": result["success"],
             "decisions": len(result["actions"]), "initial": initial, "final": info,
             "controlled_frames": frames, "episode_return": total_reward,
             "route_json_sha256": sha256(route_path),
             "kind": "successful route" if result["success"] else "best surviving prefix; not a clear"}
    if video:
        proof.update(video="route.mp4", video_sha256=sha256(output / "route.mp4"),
                     duration_seconds=(recorder.video_frames + 120) / 60., end_hold_seconds=2)
    write_json(proof_path, proof)
    return proof
