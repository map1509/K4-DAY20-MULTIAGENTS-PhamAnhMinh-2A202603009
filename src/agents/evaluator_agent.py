"""Deterministic evaluation against explicit expectations."""
from collections.abc import Mapping
import math

from .base_worker import BaseWorker, make_tools


class EvaluatorAgent(BaseWorker):
    SYSTEM_PROMPT = (
        "Evaluate against supplied criteria only. Report every check and its evidence. "
        "Never claim semantic correctness based solely on syntax or field presence."
        " Evaluate accuracy (30%), completeness (30%), clarity (20%), performance (20%). "
        "Return JSON with score (0-100), feedback, issues and suggestions. Use supplied evidence."
    )

    def __init__(self, model=None, *, workspace="."):
        tool_map = {"score": self.score, "validate": self.validate,
                    "quality_check": self.quality_check, "feedback_generator": self.feedback_generator}
        super().__init__("evaluator_agent", model, make_tools(tool_map), result_type="evaluation",
                         system_prompt=self.SYSTEM_PROMPT, tool_map=tool_map, workspace=workspace)

    @staticmethod
    def quality_check(criteria: dict) -> dict:
        """Compute weighted quality from explicit, evidence-backed 0-100 criterion scores."""
        weights = {"accuracy": .3, "completeness": .3, "clarity": .2, "performance": .2}
        if set(criteria) != set(weights):
            raise ValueError("Supply all four quality criteria")
        for value in criteria.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("Criterion scores must be finite numbers from 0 to 100")
        return {"score": sum(criteria[key] * weight for key, weight in weights.items()), "criteria": criteria}

    @staticmethod
    def feedback_generator(score: float, issues: list[str], suggestions: list[str]) -> dict:
        """Format evaluation feedback without inventing evidence or issues."""
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("score must be from 0 to 100")
        return {"score": score, "feedback": "Issues require attention" if issues else "No supplied issues",
                "issues": issues, "suggestions": suggestions}

    @staticmethod
    def score(actual, expected):
        if not isinstance(actual, Mapping) or not isinstance(expected, Mapping) or not expected:
            raise ValueError("actual and nonempty expected must be mappings")
        checks = [{"name": key, "passed": key in actual and actual[key] == value,
                   "expected": value, "actual": actual.get(key)} for key, value in expected.items()]
        passed = sum(check["passed"] for check in checks)
        return {"score": passed / len(checks), "passed": passed, "total": len(checks), "checks": checks}

    @staticmethod
    def validate(result, required_fields):
        if not isinstance(result, Mapping) or not isinstance(required_fields, list) or not required_fields:
            raise ValueError("result and nonempty required_fields list are required")
        if any(not isinstance(field, str) or not field for field in required_fields):
            raise ValueError("required_fields must contain nonempty strings")
        missing = [field for field in required_fields if field not in result]
        return {"valid": not missing, "missing": missing}
