"""Canonical game, action mapping and observation history."""
import cv2
import gym
import gym_super_mario_bros
import numpy as np
from gym_super_mario_bros.actions import SIMPLE_MOVEMENT
from nes_py.wrappers import JoypadSpace

from .wrappers import RewardFrame, SkipStack

ACTIONS = ["NOOP", "RIGHT", "RIGHT_JUMP", "RIGHT_RUN", "RIGHT_JUMP_RUN", "JUMP", "LEFT"]


def plain_info(info):
    return {k: v.item() if isinstance(v, np.generic) else v for k, v in info.items()}


class Monitor:
    def __init__(self):
        self.enabled = False
        self.frame = None
        self.controlled_frames = 0

    def record(self, frame):
        self.controlled_frames += 1
        if self.enabled:
            self.frame = frame.copy()


class ReferenceEnv:
    def __init__(self, seed=123, horizon=1200, *, world=1, stage=1):
        if not (1 <= world <= 8 and 1 <= stage <= 4):
            raise ValueError("Expected world 1–8 and stage 1–4")
        self.world, self.stage = world, stage
        cv2.setNumThreads(1)
        gym.logger.set_level(40)
        base = gym_super_mario_bros.make(f"SuperMarioBros-{world}-{stage}-v0")
        self.env = SkipStack(RewardFrame(JoypadSpace(base, SIMPLE_MOVEMENT)))
        self.env.seed(seed)
        self.monitor = Monitor()
        self.env.env.monitor = self.monitor
        self.horizon, self.steps = horizon, 0

    def reset(self):
        observation = self.env.reset()
        self.steps = 0
        info = plain_info(self.env.unwrapped._get_info())
        if info["world"] != self.world or info["stage"] != self.stage or info["flag_get"]:
            raise AssertionError("Environment did not reset to its original level entrance")
        return np.rint(observation[0] * 255).astype(np.uint8), info

    def step(self, action, render=False):
        self.monitor.enabled = render
        before = self.monitor.controlled_frames
        observation, reward, native_done, info = self.env.step(int(action))
        self.monitor.enabled = False
        self.steps += 1
        info = plain_info(info)
        timed_out = not native_done and self.steps >= self.horizon
        done = bool(native_done or timed_out)
        if timed_out:
            observation = self.env.reset()
        if done:
            self.steps = 0
        row = {"reward": float(reward), "done": done, "info": info,
               "reason": "flag" if info["flag_get"] else "terminal" if native_done else "time_limit" if timed_out else None,
               "controlled_frames": self.monitor.controlled_frames - before}
        if render:
            row["rgb"] = self.monitor.frame.tobytes()
        return np.rint(observation[0] * 255).astype(np.uint8), row

    def close(self):
        self.env.close()
