# Graduation criteria: when the loop leaves the kernel

The agentbook substrate is a **single warm kernel driven live over the runt MCP**
(see `specs/agentbook_thesis/research.md`, Decision 1). That is the right substrate
for *interactive iteration*: one process, shared memory, the host agent inside the
session firing `execute_cell` and reading the result in the same tool response. It
stops earning its keep the moment the workload stops being interactive.

When that happens, the documented path is **not** to wrap saved notebooks in headless
batch executors (papermill / nbclient). Batch-wrapping reintroduces the cold-start tax
this project exists to remove — a `.ipynb` round-trip, a harvest step, no live
introspection — while keeping all of a notebook's downsides (FR-011, A-006). The path
is to **port the hot path to a compiled service** (Rust, Go) and let the notebook stay
a notebook for the iteration it's good at.

This document names the **measurable thresholds** that trigger that port. Cross any one
of them, sustained, and the hot path graduates.

## The thresholds

### 1. Memory fan-out — kernel RSS pressure from the candidate set

**Trigger:** the live candidate set (frontier + concurrent rollout state + eval-set
copies) drives kernel resident memory past **~70% of host RAM**, *or* per-iteration
state copy/serialization time exceeds the per-iteration LLM call time (the substrate is
now spending more wall-clock moving state than doing useful work).

**Why it's the line:** GEPA holds its frontier as live Python objects in the kernel
(Decision 3). That is cheap at tens of candidates and ruinous at thousands — GC thrash
and copy overhead dominate, and a single process can no longer hold the working set.
A compiled service with an explicit, off-heap candidate store and bounded memory is the
correct answer; a bigger notebook is not.

**How to measure:** sample kernel RSS (e.g. `psutil.Process().memory_info().rss`) per
iteration against host RAM; time the state-management portion of each iteration vs. the
model-call portion.

### 2. Latency floor — per-step transit cost below ~100 ms

**Trigger:** the workload requires a sustained per-inner-step latency **below ~100 ms**,
*or* MCP tool-call + kernel-dispatch transit grows to more than ~25% of useful per-step
work.

**Why it's the line:** SC-002 budgets the warm-kernel host→next-experiment round-trip at
**under 1 second**, dominated by tool-call transit rather than file I/O or cold start —
and the substrate comfortably meets it today (a kernel `bootstrap()` measured **0.2 ms**,
and live `execute_cell` round-trips return well inside the budget). That headroom is
ample for human-in-the-loop iteration. It is *not* ample for a high-throughput serving
path that needs sub-100 ms steps: there the MCP/kernel transit becomes the bottleneck,
and an in-process compiled service removes the round-trip entirely.

**How to measure:** time `execute_cell` round-trips and isolate transit (tool-call
overhead) from compute (the cell body); compare against the required p50 step latency.

### 3. Concurrency — more than one live session at once

**Trigger:** you need to serve **more than one concurrent, independent optimization
session** (multi-tenant), or kernel-access queueing delay for a second driver becomes
material.

**Why it's the line:** one kernel is one session with a single writer (concurrent host
agents on one session are explicitly unsupported — see the T065 addendum in
`research.md`). Multi-tenant serving is out of scope for the substrate by design (A-006).
The moment the requirement is N concurrent sessions, the answer is a service that owns
its own concurrency model — not N notebooks or a queue in front of one kernel.

**How to measure:** count sustained concurrent sessions required; measure wait time for
kernel access when a second driver attaches.

## The rule

> Notebooks are for iteration. The moment the loop stops being interactive — memory it
> can't hold, latency it can't hit, or tenants it can't serve — port the hot path to a
> compiled service and keep the notebook for what it's still best at: a human and an
> agent thinking together in a live session.

These are triggers, not measured limits of the current build: today's single-tenant,
sub-second, tens-of-candidates workload sits well inside all three. This document exists
so that when a contributor proposes batch-wrapping the substrate, the answer is already
written down — cross a named threshold, port the hot path; otherwise, stay in the kernel.
