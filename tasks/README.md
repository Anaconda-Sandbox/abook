# SkillOpt target candidates — `reviewer` vs `specify`

Two real `~/.claude` skills staged as SkillOpt optimization targets, each with a
minimal **seed skill** (headroom intentionally stripped), a procedural **instance
generator**, and a **deterministic reward** checker. Each `validate.py` proves the
reward *discriminates* (good → high, weak → low, cheat → caught) using **real data
and no LLM spend**, so we can pick before paying for the full loop.

Run:
```bash
cd reviewer && python3 gen_instances.py --out instances --n 60 && python3 validate.py
cd specify  && python3 gen_instances.py --out instances --n 10 && python3 validate.py
```

## Validated reward signals (measured, not estimated)

### reviewer — planted-bug recall (fully deterministic)
| synthetic reviewer | soft (F1) | recall | precision | hard% |
|---|---|---|---|---|
| oracle (reports planted) | 1.000 | 1.00 | 1.00 | 100% |
| weak (reports ~half) | 0.711 | 0.60 | 1.00 | 32% |
| spam (reports every line) | 0.000 | 0.00 | 0.00 | 0% |

Spam cheat caught by trace-lint **60/60**. Headroom (oracle − weak) ≈ **0.29 soft**.
Reward needs **no LLM judge** — it's a pure line+category match.

### specify — spec structure (deterministic) + needs-judge (semantic)
| spec (real data) | soft | hard | failing checks |
|---|---|---|---|
| real `specs/agentbook_thesis/spec.md` | 1.00 | 1 | none |
| same spec, sections+IDs stripped | 0.10 | 0 | all structural |
| bare prose | 0.10 | 0 | all structural |

Headroom ≈ **0.90 soft**. But structure is only *half* the story — the checker emits
a `needs_judge` list it provably cannot verify (each FR genuinely testable? coverage
of the brief? outcome-vs-implementation?). Those route to the **LLM trace-judge**.

## How to choose

| | reviewer | specify |
|---|---|---|
| Reward purity | fully deterministic | deterministic structure + LLM judge for semantics |
| Cheat surface | spam findings (closed by F1 + lint) | section-stuffing (closed by structure) + vacuous FRs (**needs judge**) |
| Instances | free, combinatorial from real bug catalog | 10 real briefs (extendable) |
| Headroom | ~0.29 (tight, honest) | ~0.90 (large, structural) |
| Best at demonstrating | clean reward-driven skill learning | **why the LLM trace-judge is worth its tokens** |

**Recommendation:** build the full notebook loop on **`reviewer`** for the cleanest,
most defensible "SkillOpt learns a real skill from a deterministic signal" result, and
keep **`specify`** as the second slice that exercises the LLM trace-judge layer (the
point you raised — judge tokens are cheap relative to a long rollout). Both seeds are
ready to wire into SkillOpt's `claude_backend` rollout (Docker-free).

Next: a SkillsBench-style adapter + an agentbook notebook driving
rollout → reward(+judge) → `run_minibatch_reflect` → `apply_patch` → eval on a
held-out test split. Held-out **test**-reward delta is the headline; a flat test
curve = the skill hacked train.
