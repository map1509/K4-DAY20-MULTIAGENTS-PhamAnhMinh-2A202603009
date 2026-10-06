"""Local scoring and result-format validation tools."""
import math
import logging
from .base_tool import BaseTool


class ScoringTool(BaseTool):
    DEFAULT_CRITERIA = {"accuracy": 30, "completeness": 30, "clarity": 20, "performance": 20}

    def __init__(self):
        super().__init__("score_result", "Calculate a weighted 0-100 score from supplied criterion scores or local text heuristics")

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict) or not isinstance(input_dict.get("result", ""), str):
            raise ValueError("result must be text")
        criteria = input_dict.get("criteria", self.DEFAULT_CRITERIA)
        if not isinstance(criteria, dict) or not criteria or any(key not in self.DEFAULT_CRITERIA for key in criteria):
            raise ValueError("Invalid criteria")
        if any(isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0 for weight in criteria.values()) or sum(criteria.values()) <= 0:
            raise ValueError("Criteria need finite nonnegative weights with positive total")
        scores = input_dict.get("scores")
        if scores is not None:
            if not isinstance(scores, dict) or any(key not in scores for key in criteria):
                raise ValueError("Supply a score for each criterion")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100 for value in scores.values()):
                raise ValueError("Scores must be finite numbers from 0 to 100")
        return True

    def invoke(self, input_dict):
        try:
            self.validate_input(input_dict)
            result = input_dict.get("result", "")
            criteria = input_dict.get("criteria", self.DEFAULT_CRITERIA)
            scores = input_dict.get("scores")
            method = "supplied_scores"
            if scores is None:
                # Demonstration heuristic from the assignment, not factual accuracy verification.
                method = "text_heuristic"
                scores = ({"accuracy": min(100, len(result) * 2), "completeness": 80 if len(result) > 100 else 40,
                           "clarity": 75 if "\n" in result else 50, "performance": 90} if result else {})
            weighted = sum(scores.get(key, 0) * weight for key, weight in criteria.items()) / sum(criteria.values())
            logging.getLogger(self.name).info("Scoring result score=%.2f method=%s", weighted, method)
            return {"status": "success", "scores": scores, "weighted_score": round(weighted, 2),
                    "grade": self._score_to_grade(weighted), "method": method}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @staticmethod
    def _score_to_grade(score):
        for threshold, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
            if score >= threshold:
                return grade
        return "F"


class ValidationTool(BaseTool):
    def __init__(self):
        super().__init__("validate_result", "Check that a result contains all required fields")

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict) or not isinstance(input_dict.get("result"), dict):
            raise ValueError("result must be a dictionary")
        fields = input_dict.get("required_fields")
        if not isinstance(fields, list) or not fields or any(not isinstance(field, str) or not field for field in fields):
            raise ValueError("required_fields must be a nonempty list of field names")
        return True

    def invoke(self, input_dict):
        try:
            self.validate_input(input_dict)
            missing = [field for field in input_dict["required_fields"] if field not in input_dict["result"]]
            return {"status": "success", "valid": not missing, "missing": missing}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
