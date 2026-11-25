# Agents in BM

This project runs BDI agents on Bluetooth mesh (BM) nodes. Each node simulated by
[BMSim](https://github.com/BMSimulator/BMSim) hosts a
[SPADE-BDI](https://github.com/javipalanca/spade_bdi) agent. Agents talk to each
other **through the simulated mesh**: their messages get BLE advertising, relaying,
collisions, TTL and latency from BMSim. They do not use XMPP for this.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./setup_bmsim.sh                  # clones upstream BMSim into vendor/ and applies patches/bmsim_hooks.patch
cd mesh_agents
python run_test.py                # 5-node line, 4 hops
python run_test.py --nodes 7      # 6 hops
python run_test.py --no-relay     # negative control: nothing should be delivered
```

No external XMPP server is needed: SPADE's embedded server is started in-process.

## Test scenario

```
node0 (sensor) ── node1 ── node2 ── node3 ── node4 (sink)      9 m spacing, 11.26 m range
```

1. The sensor agent perceives a rising temperature and sends `reading(T)` to node4 (4 hops).
2. When a reading goes above 30 °C, the sink agent sends `alarm(T)` back to node0 (4 hops).
3. After the alarm, the sensor agent switches to sending `critical_reading(T)`.

Typical output: 13 messages sent and 13 delivered, every one over exactly 4 hops,
with 1–6 ms latency. All checks pass.

## Layout

| Path | Role |
|---|---|
| `mesh_agents/bridge.py` | Co-simulation bridge: runs BMSim in a thread and syncs it with the asyncio loop the agents run on |
| `mesh_agents/mesh_agent.py` | `MeshBDIAgent`: adds the `.mesh_tell(Node, Term)` and `.log(...)` actions; delivered messages become beliefs `Term[source(Node)]` |
| `mesh_agents/asl/` | AgentSpeak programs: sensor, sink, relay |
| `mesh_agents/run_test.py` | Test scenario with pass/fail checks |
| `patches/bmsim_hooks.patch` | Hooks added to BMSim: new `app_layer.py`, plus hook calls in `event_driven.py`, `scan37/38/39.py`, and `initializer.py` |
| `setup_bmsim.sh` | Fetches BMSim at the tested commit and applies the patch |

## How it works

* **Sending:** `.mesh_tell(4, reading(T))` puts a message in the agent's outbox. At the
  node's next BMSim *generation slot*, the simulator asks the bridge for a packet.
  The bridge first waits until the agent has finished reasoning, then takes one
  message from the outbox. If the outbox is empty, the slot is skipped and uses no
  airtime.
* **Receiving:** when BMSim delivers a data packet to its destination node, the
  payload is parsed back into an AgentSpeak literal and added as a belief with a
  `source(SrcNode)` annotation.
* **Time:** BMSim owns simulated time. The simulator thread blocks only at
  generation slots of nodes that host an agent. Agent reasoning takes zero
  simulated time.

## Known limitations

* Payloads are AgentSpeak strings carried in BMSim's `message.data`. BMSim models a
  fixed 38-byte packet whatever the payload. Real BM unsegmented access payloads are
  only about 11 bytes.
* Agents can send only at generation slots. Here the slot is 200 ms on the sensor and
  sink nodes, so a reply can wait up to that long before leaving the node.
* Agents on pure relay nodes don't see the packets they forward. That would need one
  more hook in the relay path of BMSim.
* BMSim quirk: a node with feature 3 (relay + generator) only sends heartbeats when
  its buffer is non-empty. So the sink's heartbeats never fire in this setup, and
  TTL stays at 127.
* spade_bdi's reasoning loop polls constantly. `MeshBDIAgent` makes idle agents sleep
  until woken; without this, the run is about 15× slower.

## License and credits

The code in this repository is licensed under the **GNU GPL v3.0 or later** (see `LICENSE`),
which keeps it compatible with python-agentspeak, the GPL-3.0 AgentSpeak engine that
SPADE-BDI depends on. Third-party projects and their licenses are listed in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

BMSim is not included in this repository. `setup_bmsim.sh` downloads it from its
upstream repository. If you use BMSim, please cite:

> Z. Hosseinkhani and M. Nabi, "BMSim: An Event-Driven Simulator for Performance
> Evaluation of Bluetooth Mesh Networks", *IEEE Internet of Things Journal*, 2023.
> https://ieeexplore.ieee.org/document/10171234
