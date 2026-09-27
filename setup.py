"""Build a ctypes-only NES library with owner-bound snapshot support."""
from pathlib import Path
import sys

from setuptools import Extension, setup

base = Path("vendor/nes-py")
sources = sorted(str(p) for p in (base / "src").rglob("*.cpp"))
flags = ["/std:c++14", "/O2"] if sys.platform == "win32" else ["-std=c++14", "-O3"]
setup(ext_modules=[Extension("mario_search._native", sources=sources,
      include_dirs=[str(base / "include")], language="c++", extra_compile_args=flags)])
