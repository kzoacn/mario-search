"""Online emulator search; every node descends from this run's entrance."""
from dataclasses import dataclass
import heapq
import time

import numpy as np


@dataclass
class Node:
    snapshot: object
    parent: object
    actions: tuple
    decisions: int
    x: int
    reward: float

    def prefix(self):
        chunks = []
        node = self
        while node is not None:
            chunks.append(node.actions)
            node = node.parent
        return [a for chunk in reversed(chunks) for a in chunk]


class BestFirstSearch:
    def __init__(self, env, seed=123, macro=4, max_nodes=6000):
        self.env, self.macro, self.max_nodes = env, macro, max_nodes
        self.rng = np.random.default_rng(seed)
        self.expanded = self.actions = self.frames = 0
        self.furthest = 40
        self.best_prefix = []
        self.best_x = 40
        self.created_nodes = 0

    def search(self, permits, progress=None):
        """Best-first search over temporally coherent buttons, without map data.

        Score favors rightward progress and lower elapsed time. The state key
        includes height, velocity, jump state and input edges; a dead branch
        leaves its alternatives in the frontier for backtracking.
        """
        env = self.env
        _,initial_info = env.reset()
        initial_x = int(initial_info['x_pos'])
        self.best_info = initial_info
        self.furthest = self.best_x = initial_x
        root = Node(env.capture(),None,(),0,initial_x,0.)
        queue = [(0.,0,root)]
        serial = 1
        seen = {}
        nodes = [root]
        self.created_nodes = 1
        best = root
        started = time.perf_counter()
        while queue and len(nodes)<self.max_nodes and permits():
            _,_,node = heapq.heappop(queue)
            self.expanded += 1
            # Run and run+jump are the efficient defaults; ordinary movement
            # and braking are also available for recovering from bad momentum.
            candidates = [3,4,2,1,0]
            for action in candidates:
                if not permits():break
                env.restore(node.snapshot)
                total = node.reward
                sequence = []
                dead = False
                for _ in range(self.macro):
                    if not permits():break
                    _, row = env.step(action)
                    sequence.append(action)
                    self.actions += 1
                    self.frames += row['controlled_frames']
                    total += row['reward']
                    info = row['info']
                    self.furthest = max(self.furthest,info['x_pos'])
                    if row['done']:
                        if info['flag_get']:
                            prefix = node.prefix()+sequence
                            for saved in nodes:saved.snapshot.close()
                            return {'success':True,'actions':prefix,'decisions':len(prefix),
                                    'search_actions':self.actions,'expanded':self.expanded,
                                    'seconds':time.perf_counter()-started,'furthest_x':self.furthest,
                                    'reason':'native_success','route_info':info,'created_nodes':len(nodes),
                                    'controlled_frames':self.frames}
                        dead = True
                        break
                if dead or not sequence or not permits():continue
                ram = env.env.unwrapped.ram
                # The planner uses internal game state for search deduplication.
                key = (info['x_pos']//6,info['y_pos']//6,int(ram[0x1d]),
                       int(ram[0x57])//8,int(ram[0x9f])//8,action)
                decisions = node.decisions+len(sequence)
                if decisions >= env.horizon or (key in seen and seen[key]<=decisions):continue
                seen[key] = decisions
                child = Node(env.capture(),node,tuple(sequence),decisions,info['x_pos'],total)
                nodes.append(child)
                self.created_nodes = len(nodes)
                priority = -child.x+.1*decisions
                heapq.heappush(queue,(priority,serial,child))
                serial += 1
                if child.x>best.x:
                    best=child
                    self.best_x=child.x
                    self.best_prefix=child.prefix()
                    self.best_info=info
            if progress:progress(self)
        prefix = best.prefix()
        env.restore(best.snapshot)
        from .environment import plain_info
        route_info = plain_info(env.env.unwrapped._get_info())
        reason = 'frontier_exhausted' if not queue else 'node_limit' if len(nodes)>=self.max_nodes else 'deadline'
        for saved in nodes:saved.snapshot.close()
        return {'success':False,'actions':prefix,'decisions':len(prefix),
                'search_actions':self.actions,'expanded':self.expanded,
                'seconds':time.perf_counter()-started,'furthest_x':self.furthest,
                'reason':reason,'route_info':route_info,'created_nodes':len(nodes),
                'controlled_frames':self.frames,'best_surviving_x':best.x}
