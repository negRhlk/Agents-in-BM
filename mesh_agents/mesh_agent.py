# SPDX-License-Identifier: GPL-3.0-or-later
"""A SPADE-BDI agent whose communication goes over the simulated Bluetooth mesh.

AgentSpeak side:
  .mesh_tell(DestNode, Term)   queue Term for transmission to mesh node DestNode.
                               It leaves on this node's next BMSim generation slot.
  On delivery, the receiver gets the belief  Term[source(SrcNode)]
  (same shape as a regular `.send(..., tell, ...)`, but the source is a mesh address).
"""
import asyncio
from collections import deque

import agentspeak as asp
from spade_bdi.bdi import BDIAgent
from spade_bdi.bdi_behaviour import BDIBehaviour
from spade_bdi.utils import parse_literal


class IdleAwareBDIBehaviour(BDIBehaviour):
    """spade_bdi's behaviour busy-polls; with many agents that starves the simulator
    thread (GIL). When there is nothing to reason about, sleep until woken (new percept)
    or for at most 50 ms (so XMPP messages are still picked up)."""

    async def run(self):
        agent = self.agent
        if agent.bdi_enabled and agent.is_quiescent() and self.mailbox_size() == 0:
            agent._wake.clear()
            try:
                await asyncio.wait_for(agent._wake.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass
        await super().run()


class MeshBDIAgent(BDIAgent):
    def __init__(self, jid, password, asl, node_id, bridge_log=None, **kwargs):
        # must exist before super().__init__, which registers the custom actions
        self.node_id = node_id
        self.mesh_outbox = deque()
        self._bridge_log = bridge_log or (lambda *a: None)
        self._wake = asyncio.Event()
        super().__init__(jid, password, asl, **kwargs)

    def add_behaviour(self, behaviour, template=None):
        if type(behaviour) is BDIBehaviour:
            behaviour.__class__ = IdleAwareBDIBehaviour
        super().add_behaviour(behaviour, template)

    def wake(self):
        self._wake.set()

    def add_custom_actions(self, actions):
        @actions.add(".mesh_tell", 2)
        def _mesh_tell(agent, term, intention):
            dest = asp.grounded(term.args[0], intention.scope)
            content = asp.freeze(term.args[1], intention.scope, {})
            self.mesh_outbox.append((int(dest), asp.asl_str(content)))
            yield

        @actions.add(".log")
        def _log(agent, term, intention):
            parts = [asp.asl_str(asp.freeze(a, intention.scope, {})) for a in term.args]
            self._bridge_log(self.node_id, " ".join(p.strip('"') for p in parts))
            yield

    # ---- called on the asyncio loop by the bridge ----
    def perceive_mesh_message(self, src_node: int, payload: str):
        functor, args = parse_literal(payload)
        lit = asp.Literal(functor, tuple(args) if args else ())
        lit = lit.with_annotation(asp.Literal("source", (src_node,)))
        self.bdi_intention_buffer.append(
            (asp.Trigger.addition, asp.GoalType.belief, lit, asp.runtime.Intention())
        )
        self.wake()

    def is_quiescent(self) -> bool:
        return not self.bdi_intention_buffer and not any(self.bdi_agent.intentions)

    async def wait_quiescent(self, timeout=2.0, poll=0.002):
        """Wait until the BDI reasoner has handled all pending events/intentions."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        stable = 0
        while loop.time() < deadline:
            stable = stable + 1 if self.is_quiescent() else 0
            if stable >= 3:
                return True
            await asyncio.sleep(poll)
        return False
