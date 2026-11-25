// SPDX-License-Identifier: GPL-3.0-or-later
// Sink agent: monitors readings; if a reading exceeds the threshold it
// alarms the reporting node (once), again over the mesh.
threshold(30).

+reading(T)[source(S)] : threshold(Th) & T > Th & not alarmed(S) <-
    .log("reading", T, "from node", S, "exceeds", Th, "-> alarm back to node", S);
    +alarmed(S);
    .mesh_tell(S, alarm(T)).

+reading(T)[source(S)] <-
    .log("reading", T, "from node", S).

+critical_reading(T)[source(S)] <-
    .log("CRITICAL reading", T, "from node", S).
