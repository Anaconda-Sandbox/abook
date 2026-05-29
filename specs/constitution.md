# agentbook Constitution

> A self-evolving notebook — evaluation and improvement as one loop.
> This constitution governs every spec, plan, and implementation in the repo.

## Design Philosophy

<!-- Auto-injected from ~/.claude/skills/specify/principles/. To customize, edit the principle files. -->

### Simplicity
Prefer the simplest solution that could work. Complexity must justify itself.

### First Principles
Decompose to fundamentals before building. Don't inherit assumptions — derive from ground truth.

### Scaling Laws
Design for scaling behavior, not fixed capacity. Understand how the system behaves as inputs grow.

### Generalizability
Build general systems, not one-off solutions. Solve the class of problems, not just the instance.

### Agent Autonomy
Guide, don't micromanage. Specify outcomes and constraints — let agents figure out how. Over-specifying kills emergence.

### Execution Ladder
Always start with the cheapest, fastest execution tier. Escalate only when the lower tier can't solve the problem.

### Convergent Discovery
Write from multiple perspectives. Compare. Find gaps. Clarity emerges from the contradictions.

### Next Action
Every output must make the user's position clear. If there is a next action, show it. If the workflow is complete, say so. The only bad state is ambiguity — where the user doesn't know whether they're done or stuck.

## Core Principles

### I. Real Data Only (hard invariant)

Every cell in a deliverable notebook MUST read from a real source — a real git repo, a real API call, a real web search, a real file walk, or a real on-disk fixture. Every deliverable notebook MUST end with a **Data sources** section citing the real paths, URLs, commands, or queries behind each non-trivial claim. Fabricated or synthesized data — `random.gauss(...)` "demo rows", hand-rolled "let's pretend" placeholders, invented scores or traces — is forbidden in any deliverable (notebook, report, plot, comparison table). The one exception is a minimal unit-test fixture exercising a specific schema branch.

**Rationale**: agentbook's entire value is measurement. A fabricated score is worse than no score — it launders a guess into a number the outer loop will then "optimize" against. If the real source doesn't exist yet, say so and stop; don't substitute fake data.

### II. The Loop's Architectural Invariants (hard, gate-enforced)

Three invariants are non-negotiable and the `/specify plan` Constitution Check MUST block on each:

1. **Inner loop never self-rewrites the substrate.** An inner-loop iteration MUST NOT edit the notebook it runs in or the agentbook codebase. The inner loop mutates only the artifact under evolution.
2. **One declared slice per run.** Each optimization run mutates exactly one declared harness slice (system prompt, skill document, scaffolding routine, tool config). Crossing slices is an outer-loop decision, never an inner-loop privilege.
3. **Substrate-first; don't batch-wrap.** When the workload outgrows interactive iteration, the path is to port the hot path to a compiled service and let the notebook stay a notebook — never to wrap notebooks in headless batch executors. Graduation thresholds (memory fan-out, latency floor, concurrency) MUST be documented.

**Rationale**: These three define what makes the harness *genuinely* self-evolving while staying safe and measurable. Genuine self-evolution lives in the outer loop editing agentbook between sessions — not in any in-kernel self-rewrite.

### III. Code Quality

All code MUST pass `ruff` lint (rules E, W, F, I, B, C4, UP; line length 120) and `ruff format` (double quotes, space indent). All code MUST type-check under `mypy` (Python 3.10 baseline). Functions and modules MUST have a single, clear responsibility. No bare `except: pass` — an intentional swallow needs a one-line reason comment. Delete unused locals, imports, and globals in the same edit that orphaned them.

**Rationale**: The repo ships as an installable package (`agentbook`) and is read by both humans and the evolving agent. Lint and type cleanliness keep the harness legible to the thing improving it.

### IV. Testing Standards

New functionality in the library (`src/agentbook`) MUST have corresponding tests under `tests/`, runnable with `pytest`. Unit tests MAY mock. Any CLI, end-to-end, or integration validation MUST hit real services with real credentials — never fake/mock credentials for manual or CLI validation. Tests MUST be isolated and deterministic. Strict TDD is not required.

**Rationale**: Mocked integration tests give false confidence in a project whose deliverable is a live MCP-driven kernel session. Real-service validation is the only validation that proves the substrate works.

### V. Thin Harness, Fat Skills

Push intelligence up into markdown/skill artifacts; push execution down into narrow, fast, deterministic code. Classify each step before building: **latent** (judgment, synthesis, reflection → LLM) vs. **deterministic** (counting, aggregation, scoring math → code/SQL/CLI). Don't force deterministic work into latent space (it hallucinates) or latent work into code (it goes brittle).

**Rationale**: The inner loop's thin LLM is for reflection; the substrate around it should be boring and fast. Misclassifying the two is the most common way this kind of loop degrades.

### VI. Explicit Over Implicit

Function behaviour MUST be predictable from its signature. Side effects MUST be documented and minimized. The harness slice under evolution, the LLM-call budget, and the eval set MUST be explicitly declared at session setup — never inferred or silently mutated mid-run.

**Rationale**: An optimization loop is only trustworthy if its inputs are pinned. Silent drift in the eval set or budget invalidates every cross-iteration comparison.

## Quality Gates

All code MUST pass before merge:

- `pre-commit` hooks: trailing-whitespace, end-of-file-fixer, check-yaml/json/toml, check-merge-conflict, debug-statements.
- `ruff` (with `--fix`) and `ruff-format`.
- `mypy` (`--ignore-missing-imports`).
- Full `pytest` suite (with `pytest-cov` where coverage is tracked).
- GitHub Actions workflows MUST declare a `permissions:` block (default `contents: read`).
- Deliverable notebooks MUST carry a **Data sources** section (Principle I).

## Development Workflow

1. **Specification**: Define requirements and acceptance criteria before coding (`/specify spec`).
2. **Plan**: Translate the spec into architecture; the Constitution Check gate must pass (`/specify plan`).
3. **Implementation**: Write the minimal code that satisfies the spec and the loop invariants.
4. **Test**: Unit tests may mock; CLI/E2E validation hits real services with real credentials.
5. **Refactor**: Improve quality while keeping tests green and lint/type clean.
6. **Review**: Submit PR against the quality gates above.

## Governance

**Amendment Process**:

1. Propose changes via PR with rationale.
2. Obtain approval from project maintainers.
3. Update version according to semantic versioning.

**Versioning Policy**:

- MAJOR: Backward-incompatible principle changes or removals.
- MINOR: New principles or materially expanded guidance.
- PATCH: Clarifications, wording improvements, typo fixes.

**Version**: 1.0.0 | **Ratified**: 2026-05-28 | **Last Amended**: 2026-05-28
