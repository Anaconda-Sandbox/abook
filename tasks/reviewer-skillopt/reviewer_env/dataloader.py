from __future__ import annotations

from skillopt.datasets.base import SplitDataLoader


class SkillsBenchReviewerDataLoader(SplitDataLoader):
    """Reviewer instances from split_dir/{train,val,test}/items.json (split_dir mode)."""
