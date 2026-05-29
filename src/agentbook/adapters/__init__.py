"""Optimizer adapters.

Each adapter wraps a third-party optimizer library so it satisfies the
:class:`agentbook.contract.Optimizer` Protocol. The substrate driver
(:func:`agentbook.loop.run_iteration`) is written once against that Protocol
and is identical for every adapter — only the adapter's state shape differs
(kernel-resident for GEPA, on-disk for SkillOpt).
"""
