// SPDX-License-Identifier: GPL-3.0-or-later
// Sensor agent: reports temperature to the sink over the mesh.
// After being alarmed by the sink it switches to "critical" reporting.
sink(4).
mode(normal).

+temperature(T) : mode(normal) & sink(S) <-
    .mesh_tell(S, reading(T)).

+temperature(T) : mode(critical) & sink(S) <-
    .mesh_tell(S, critical_reading(T)).

+alarm(T)[source(S)] <-
    .log("got alarm(", T, ") from node", S, "-> switching to critical mode");
    -mode(normal);
    +mode(critical).
