# SPDX-License-Identifier: GPL-3.0-or-later
"""Co-simulation bridge between BMSim (discrete-event, runs in a worker thread)
and SPADE-BDI agents (asyncio event loop).

Time model (lockstep at decision points):
  * BMSim owns simulated time.
  * At every generation slot of a node that hosts an agent, the simulator BLOCKS,
    the bridge updates the agent's percepts, waits until the agent's reasoner is
    quiescent, and takes at most one message from its mesh outbox.
    An empty outbox means the slot is skipped (no airtime).
  * Deliveries are pushed to the destination agent as beliefs. Since they are
    scheduled on the same loop in FIFO order, an agent always sees everything
    delivered to it before its next generation slot is decided.
  * Agent reasoning therefore takes zero simulated time.
"""
import asyncio
import os
import random
import runpy
import sys
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BMSIM_CODES = os.path.join(HERE, "..", "vendor", "BMSim", "codes")


@dataclass
class MeshEvent:
    kind: str          # "TX" or "RX"
    t: float           # simulated time (ms)
    node: int          # node where it happened
    peer: int          # destination (TX) or source (RX)
    payload: str
    seq: int = 0
    hops: int = 0
    latency: float = 0.0


@dataclass
class MeshBridge:
    loop: asyncio.AbstractEventLoop
    agents: dict                     # node_id -> MeshBDIAgent
    environment: object = None       # callable(node_id, t, agent) to update percepts
    events: list = field(default_factory=list)
    agent_logs: list = field(default_factory=list)
    sim_time: float = 0.0
    verbose: bool = True

    # ---------------- logging ----------------
    def agent_log(self, node_id, text):
        self.agent_logs.append((self.sim_time, node_id, text))
        if self.verbose:
            print(f"[t={self.sim_time:8.1f} ms] node{node_id} agent: {text}", flush=True)

    # ---------------- hooks called from the BMSim thread ----------------
    def on_generate(self, node_id, t, destination, data, ttl):
        agent = self.agents.get(node_id)
        if agent is None:
            return None  # nodes without an agent produce no application traffic
        fut = asyncio.run_coroutine_threadsafe(self._decide(agent, node_id, t), self.loop)
        item = fut.result(timeout=30)
        if item is None:
            return None
        dest, payload = item
        self.events.append(MeshEvent("TX", t, node_id, dest, payload))
        if self.verbose:
            print(f"[t={t:8.1f} ms] node{node_id} --TX--> node{dest}: {payload}  (TTL={ttl})", flush=True)
        return [dest], {"payload": payload, "ttl0": ttl}, ttl

    def on_deliver(self, node_id, msg, t):
        data = msg.data
        if not isinstance(data, dict) or "payload" not in data:
            return  # BMSim's default random-int traffic, not agent traffic
        hops = data["ttl0"] - msg.TTL + 1
        ev = MeshEvent("RX", t, node_id, msg.source, data["payload"], msg.seq_number, hops,
                       t - msg.generation_time)
        self.events.append(ev)
        if self.verbose:
            print(f"[t={t:8.1f} ms] node{node_id} <--RX-- node{msg.source}: {ev.payload}  "
                  f"(seq={ev.seq}, hops={hops}, latency={ev.latency:.1f} ms)", flush=True)
        agent = self.agents.get(node_id)
        if agent is not None:
            self.loop.call_soon_threadsafe(self._deliver, agent, t, msg.source, data["payload"])

    # ---------------- runs on the asyncio loop ----------------
    def _deliver(self, agent, t, src, payload):
        self.sim_time = t
        agent.perceive_mesh_message(src, payload)

    async def _decide(self, agent, node_id, t):
        await agent.wait_quiescent()  # finish reacting to earlier deliveries (under their timestamps)
        self.sim_time = t
        if self.environment is not None:
            self.environment(node_id, t, agent)
            agent.wake()
        if not await agent.wait_quiescent():
            print(f"warning: node{node_id} agent not quiescent at t={t:.1f}", flush=True)
        return agent.mesh_outbox.popleft() if agent.mesh_outbox else None

    # ---------------- simulator thread ----------------
    def run_bmsim(self, scenario: dict, outdir: str, seed: int = 1):
        """Run BMSim's event_driven.py unmodified-in-structure, with our hooks installed."""
        os.makedirs(outdir, exist_ok=True)
        os.environ.setdefault("MPLBACKEND", "Agg")
        codes = os.path.abspath(BMSIM_CODES)
        if codes not in sys.path:
            sys.path.insert(0, codes)
        random.seed(seed)
        np.random.seed(seed)
        import app_layer
        app_layer.SCENARIO = scenario
        app_layer.on_generate = self.on_generate
        app_layer.on_deliver = self.on_deliver
        cwd = os.getcwd()
        os.chdir(outdir)  # BMSim writes its logs / topology.png to the CWD
        try:
            runpy.run_path(os.path.join(codes, "event_driven.py"), run_name="__bmsim__")
        finally:
            os.chdir(cwd)
