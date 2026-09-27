"""A small deterministic world checks branch restoration and backtracking."""
import numpy as np

from mario_search.search import BestFirstSearch


class State:
    def __init__(self, node):
        self.node = node
        self.closed = False

    def close(self):
        self.closed = True


class World:
    horizon = 20

    def __init__(self):
        self.env = self
        self.unwrapped = self
        self.ram = np.zeros(2048, dtype=np.uint8)
        self.saved = []
        self.node = 0

    def reset(self):
        self.node = 0
        return None, self._get_info()

    def _get_info(self):
        return {"x_pos": [40, 100, 70, 150][self.node], "y_pos": 80, "flag_get": self.node == 3}

    def capture(self):
        state = State(self.node)
        self.saved.append(state)
        return state

    def restore(self, state):
        assert not state.closed
        self.node = state.node

    def step(self, action):
        dead = False
        if self.node == 0:
            if action == 3:
                self.node = 1  # Greedy forward branch is a trap.
            elif action == 4:
                self.node = 2
        elif self.node == 1:
            dead = True
        elif self.node == 2 and action == 3:
            self.node = 3
        return None, {"reward": 0, "done": dead or self.node == 3,
                      "info": self._get_info(), "controlled_frames": 4}


def test_search_backtracks_and_returns_the_successful_parent_chain():
    env = World()
    result = BestFirstSearch(env, macro=1).search(lambda: True)
    assert result["success"]
    assert result["actions"] == [4, 3]
    assert result["expanded"] >= 3
    assert all(s.closed for s in env.saved)


def test_search_keeps_a_replayable_prefix_at_deadline():
    env = World()
    checks = [0]

    def permits():
        checks[0] += 1
        return checks[0] < 30

    result = BestFirstSearch(env, macro=1).search(permits)
    assert not result["success"]
    assert result["reason"] == "deadline"
    assert all(s.closed for s in env.saved)
    env.reset()
    for action in result["actions"]:
        _, row = env.step(action)
        assert not row["done"]
    assert env._get_info() == result["route_info"]
