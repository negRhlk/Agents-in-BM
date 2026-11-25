# SPDX-License-Identifier: GPL-3.0-or-later
"""Feasibility test: SPADE-BDI agents on the nodes of a BMSim multi-hop BM network.

Topology (line, 9 m spacing, 11.26 m radio range -> each node only hears its neighbours):

    node0 ---- node1 ---- node2 ---- node3 ---- node4
   (sensor)   (relay)    (relay)    (relay)    (sink)

Scenario:
  * node0's agent perceives a rising temperature (25 C + 1 C per simulated second)
    and reports each new value to node4 with .mesh_tell  -> 4 hops through relays.
  * node4's agent alarms node0 once a reading exceeds 30 C -> 4 hops back.
  * node0's agent, on the alarm belief, switches to critical mode and sends
    critical_reading(T) from then on.

Usage:
  python run_test.py              # the test
  python run_test.py --no-relay   # negative control: middle nodes don't relay
"""
import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict

import spade

from bridge import MeshBridge
from mesh_agent import MeshBDIAgent

HERE = os.path.dirname(os.path.abspath(__file__))
ASL = os.path.join(HERE, "asl")

# BMSim feature codes (see vendor/BMSim/codes/initializer.py)
JUST_RELAY, JUST_GENERATION, RELAY_AND_GENERATION = 1, 2, 3


def build_scenario(n_nodes, sim_ms, no_relay):
    sensor, sink = 0, n_nodes - 1
    middle_feature = JUST_GENERATION if no_relay else JUST_RELAY
    features = {i: middle_feature for i in range(1, n_nodes - 1)}
    features[sensor] = RELAY_AND_GENERATION
    features[sink] = RELAY_AND_GENERATION
    return {
        "positions": [(9 * i, 0) for i in range(n_nodes)],
        "node_range": 11.26,
        "execution_time": sim_ms,
        "sink": sink,
        "features": features,
        # short slots = low queueing delay for agent messages; empty slots cost no airtime
        "generation_interval": {sensor: 200, sink: 200},
    }


def temperature_environment(sensor_id):
    def env(node_id, t, agent):
        if node_id == sensor_id:
            agent.bdi.set_belief("temperature", 25 + int(t // 1000))
    return env


async def main(args):
    n = args.nodes
    sensor, sink = 0, n - 1
    loop = asyncio.get_running_loop()
    bridge = MeshBridge(loop, agents={}, environment=temperature_environment(sensor))

    asl_for = {sensor: "sensor.asl", sink: "sink.asl"}
    for i in range(n):
        a = MeshBDIAgent(f"node{i}@localhost", "secret", os.path.join(ASL, asl_for.get(i, "relay.asl")),
                         node_id=i, bridge_log=bridge.agent_log)
        await a.start(auto_register=True)
        bridge.agents[i] = a
    if sink != 4:  # sensor.asl hard-codes sink(4); patch belief for other sizes
        bridge.agents[sensor].bdi.set_belief("sink", sink)
    print(f"started {n} SPADE-BDI agents: {[str(a.jid) for a in bridge.agents.values()]}")

    scenario = build_scenario(n, args.sim_ms, args.no_relay)
    outdir = os.path.join(HERE, "runs", "no_relay" if args.no_relay else "multihop")
    t0 = time.time()
    await loop.run_in_executor(None, bridge.run_bmsim, scenario, outdir, args.seed)
    wall = time.time() - t0

    for a in bridge.agents.values():
        await a.stop()

    # ---------------- report ----------------
    ev = bridge.events
    tx = [e for e in ev if e.kind == "TX"]
    rx = [e for e in ev if e.kind == "RX"]
    up = [e for e in rx if e.node == sink and e.peer == sensor]
    down = [e for e in rx if e.node == sensor and e.peer == sink]
    crit = [e for e in up if e.payload.startswith("critical_reading")]
    print("\n================ summary ================")
    print(f"simulated {args.sim_ms/1000:.1f} s of BM network in {wall:.1f} s wall time")
    print(f"agent messages sent: {len(tx)}, delivered: {len(rx)}  (PDR {len(rx)/max(len(tx),1):.0%})")
    if rx:
        print(f"hop counts observed: {sorted({e.hops for e in rx})}; "
              f"latency min/avg/max: {min(e.latency for e in rx):.1f} / "
              f"{sum(e.latency for e in rx)/len(rx):.1f} / {max(e.latency for e in rx):.1f} ms")
    print(f"sensor->sink deliveries: {len(up)}  sink->sensor deliveries: {len(down)}  "
          f"critical readings after alarm: {len(crit)}")
    with open(os.path.join(outdir, "agent_trace.json"), "w") as f:
        json.dump({"scenario": {k: (v if k != "features" else {str(a): b for a, b in v.items()})
                                for k, v in scenario.items()},
                   "events": [asdict(e) for e in ev],
                   "agent_logs": bridge.agent_logs}, f, indent=1)
    print(f"trace + BMSim logs in {outdir}")

    if args.no_relay:
        ok = len(rx) == 0
        print("NEGATIVE CONTROL", "PASSED (nothing delivered without relays)" if ok else "FAILED")
    else:
        checks = {
            "sensor readings reached sink over multiple hops": bool(up) and all(e.hops == n - 1 for e in up),
            "sink's alarm reached sensor over multiple hops": bool(down) and all(e.hops == n - 1 for e in down),
            "sensor agent changed behaviour after alarm": bool(crit),
        }
        for k, v in checks.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        ok = all(checks.values())
    return ok


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--nodes", type=int, default=5)
    p.add_argument("--sim-ms", type=int, default=12000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--no-relay", action="store_true")
    args = p.parse_args()
    result = {}

    async def _wrapped():
        result["ok"] = await main(args)

    spade.run(_wrapped(), embedded_xmpp_server=True)
    sys.exit(0 if result.get("ok") else 1)
