"""Owner-bound, exact in-process snapshots for the reference NROM emulator.

Only explicitly enabled search processes use the additional C ABI. Ordinary
evaluation workers import the unmodified installed nes-py library.
"""
import ctypes
import hashlib
from pathlib import Path

import numpy as np

from .environment import ReferenceEnv


def enable_snapshots():
    import nes_py.nes_env as module
    if hasattr(module._LIB, 'CaptureSnapshot'):
        return module._LIB
    from importlib.machinery import EXTENSION_SUFFIXES
    paths = [Path(__file__).with_name('_native'+suffix) for suffix in EXTENSION_SUFFIXES]
    paths = [path for path in paths if path.is_file()]
    if len(paths) != 1:
        raise RuntimeError('Native snapshot library is missing. Run: python -m pip install -e .')
    lib = ctypes.cdll.LoadLibrary(str(paths[0]))
    for name in ('Width','Height','Initialize','Controller','Screen','Memory',
                 'Reset','Step','Backup','Restore','Close'):
        getattr(lib, name).argtypes = getattr(module._LIB, name).argtypes
        getattr(lib, name).restype = getattr(module._LIB, name).restype
    lib.CaptureSnapshot.argtypes = [ctypes.c_void_p]
    lib.CaptureSnapshot.restype = ctypes.c_void_p
    lib.RestoreSnapshot.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.RestoreSnapshot.restype = ctypes.c_bool
    lib.FreeSnapshot.argtypes = [ctypes.c_void_p]
    lib.FreeSnapshot.restype = None
    module._LIB = lib
    return lib


class Snapshot:
    def __init__(self, owner):
        self.owner = owner
        self.pointer = owner.library.CaptureSnapshot(owner.env.unwrapped._env)
        if not self.pointer:
            raise MemoryError('Native snapshot allocation failed')
        self.states = owner.env.states.copy()
        self.steps = owner.steps
        self.fields = []
        layer = owner.env
        while True:
            attrs = {k:getattr(layer,k) for k in ('curr_score','current_x','_elapsed_steps',
                '_has_reset','_time_last','_x_position_last','done') if k in vars(layer)}
            self.fields.append((layer,attrs))
            if 'env' not in vars(layer):
                break
            layer = layer.env
        self.ram_sha256 = hashlib.sha256(owner.env.unwrapped.ram.tobytes()).hexdigest()

    def close(self):
        if self.pointer:
            self.owner.library.FreeSnapshot(self.pointer)
            self.pointer = None

    def __del__(self):
        self.close()


class SearchEnv(ReferenceEnv):
    def __init__(self, seed=123, horizon=1200, *, world=1, stage=1):
        self.library = enable_snapshots()
        super().__init__(seed,horizon,world=world,stage=stage)
        # This capture implementation assumes an immutable CHR-ROM cartridge.
        from gym_super_mario_bros._roms import rom_path
        rom = Path(rom_path(lost_levels=False,rom_mode='vanilla')).read_bytes()
        mapper = (rom[6]>>4) | (rom[7]&0xf0)
        if mapper != 0 or rom[5] == 0:
            raise ValueError('Snapshots only support NROM with immutable CHR ROM')

    def capture(self):
        return Snapshot(self)

    def restore(self, snapshot):
        if snapshot.owner is not self or not snapshot.pointer:
            raise ValueError('Snapshot must be live and belong to this emulator')
        if not self.library.RestoreSnapshot(self.env.unwrapped._env,snapshot.pointer):
            raise RuntimeError('Native snapshot owner mismatch')
        for layer,attrs in snapshot.fields:
            for key,value in attrs.items():
                setattr(layer,key,value)
        self.env.states[:] = snapshot.states
        self.steps = snapshot.steps
        return np.rint(self.env.states*255).astype(np.uint8)
