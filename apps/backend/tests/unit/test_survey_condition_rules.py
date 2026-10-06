from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.survey.application.condition_rules import (
    SurveyConditionRuleError, parse_condition_rule,
)


class SurveyConditionRuleTests(unittest.TestCase):
    def test_nested_rule_is_bounded_and_returns_ordered_leaves(self) -> None:
        first, second = uuid.uuid4(), uuid.uuid4()
        leaves = parse_condition_rule({"all": [
            {"question_ref": str(first), "operator": "EQUALS", "value": "YES"},
            {"any": [
                {"question_ref": str(second), "operator": "ANSWERED"},
                {"question_ref": str(first), "operator": "IN", "value": ["A", "B"]},
            ]},
        ]})
        self.assertEqual(tuple(leaf.question_ref for leaf in leaves),
                         (first, second, first))

    def test_unknown_ambiguous_and_unbounded_rules_are_rejected(self) -> None:
        ref = str(uuid.uuid4())
        invalid = (
            {},
            {"question_ref": ref, "operator": "ANSWERED", "value": True},
            {"question_ref": ref, "operator": "EQUALS"},
            {"question_ref": ref, "operator": "IN", "value": []},
            {"all": [{"question_ref": ref, "operator": "ANSWERED"}], "any": []},
            {"all": []},
            {"question_ref": ref, "operator": "EQUALS", "value": {}},
        )
        for rule in invalid:
            with self.subTest(rule=rule), self.assertRaises(SurveyConditionRuleError):
                parse_condition_rule(rule)


if __name__ == "__main__":
    unittest.main()
