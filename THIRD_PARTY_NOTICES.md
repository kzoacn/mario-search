# Third-party code and media

- `vendor/nes-py/` contains the C++ emulator from [nes-py 8.2.1](https://github.com/Kautenja/nes-py), pinned to `b6f4e26a96cf1dc2329b3b45b9f785dd7dbb30c6`, copyright Christian Kauten, MIT. Local changes add `CaptureSnapshot`, `RestoreSnapshot`, and `FreeSnapshot`, with controller state and owner checks. The original license is in `third_party/nes-py.LICENSE`.
- `mario_search/wrappers.py` adapts image/reward wrappers from [Viet Nguyen's Super-mario-bros-PPO-pytorch](https://github.com/vietnh1009/Super-mario-bros-PPO-pytorch), commit `ab4248d715346c6adc33c2157455e2b98c130bcc`, MIT. PPO, PyTorch and level-specific maze termination rules are not included. The original license is in `third_party/upstream-wrappers.LICENSE`.
- `gym`, `gym-super-mario-bros`, NumPy, OpenCV and pyglet are separately installed dependencies under their respective licenses.
- Mario and the game graphics belong to Nintendo. The GIFs show recorded gameplay for this research demonstration. The repository contains no ROM files and is not affiliated with Nintendo.
