import hashlib

import numpy as np
import pytest

from mario_search.environment import ReferenceEnv
from mario_search.native import SearchEnv


def trace(env, actions):
    rows = []
    for action in actions:
        pixels, row = env.step(action)
        rows.append((hashlib.sha256(pixels.tobytes()).hexdigest(), row,
                     hashlib.sha256(env.env.unwrapped.ram.tobytes()).hexdigest()))
    return rows


def test_snapshot_library_matches_reference_and_restores_nested_states():
    actions = np.repeat(np.random.default_rng(73).choice([1, 2, 3, 4], 30), 3)
    reference = ReferenceEnv(horizon=67)
    try:
        initial, _ = reference.reset()
        expected = trace(reference, actions)
    finally:
        reference.close()
    search = SearchEnv(horizon=67)
    other = None
    snapshots = []
    try:
        pixels, _ = search.reset()
        np.testing.assert_array_equal(pixels, initial)
        assert trace(search, actions) == expected
        search.reset()
        for action in [3, 4, 3, 2]:
            search.step(action)
            snapshots.append(search.capture())
        expected_traces = []
        for state in snapshots:
            search.restore(state)
            expected_traces.append(trace(search, actions[:25]))
        for state, expected in zip(reversed(snapshots), reversed(expected_traces)):
            search.restore(state)
            assert hashlib.sha256(search.env.unwrapped.ram.tobytes()).hexdigest() == state.ram_sha256
            assert trace(search, actions[:25]) == expected
        other = SearchEnv()
        with pytest.raises(ValueError):
            other.restore(snapshots[0])
        snapshots[0].close()
        with pytest.raises(ValueError):
            search.restore(snapshots[0])
    finally:
        for state in snapshots:
            state.close()
        if other:
            other.close()
        search.close()


def test_finite_horizon_resets_observation_and_emits_terminal():
    env = ReferenceEnv(horizon=2)
    try:
        initial, _ = env.reset()
        _, first = env.step(0)
        obs, last = env.step(0)
        assert not first["done"]
        assert last["done"] and last["reason"] == "time_limit"
        np.testing.assert_array_equal(initial, obs)
    finally:
        env.close()
