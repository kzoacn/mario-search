"""Convert verified MP4 recordings to compact README GIFs with ffmpeg."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recordings", type=Path, required=True,
                        help="Directory containing <level>/route.mp4")
    parser.add_argument("--output", type=Path, default=Path("assets"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for level in ["1-1", "1-4", "2-2"]:
        source = args.recordings / level / "route.mp4"
        info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(source)]))["streams"][0]
        crop = "crop=768:720:0:48," if info["width"] == info["height"] == 768 else ""
        graph = crop + "setpts=(PTS-STARTPTS)/2,fps=12,scale=384:360:flags=neighbor,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
        target = args.output / f"world-{level}.gif"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(source),
                        "-filter_complex", graph, "-loop", "0", str(target)], check=True)
        rows.append({"level": level, "file": target.name, "bytes": target.stat().st_size,
                     "gif_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                     "source_video_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "speed": 2, "fps": 12, "size": [384, 360]})
    (args.output / "demos.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
