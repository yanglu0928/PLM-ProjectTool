"""Bounded, deterministic Survey question display-condition rules."""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field


_GROUPS = frozenset({"all", "any"})
_VALUE_OPERATORS = frozenset({"EQUALS", "NOT_EQUALS", "IN", "NOT_IN"})
_UNARY_OPERATORS = frozenset({"ANSWERED", "NOT_ANSWERED"})
_MISSING = object()


class SurveyConditionRuleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SurveyConditionLeaf:
    question_ref: uuid.UUID
    operator: str
    value: object = field(default=_MISSING, repr=False)

    @property
    def has_value(self) -> bool:
        return self.value is not _MISSING


def parse_condition_rule(rule: object) -> tuple[SurveyConditionLeaf, ...]:
    """Parse the frozen bounded AST and return its referenced-question leaves."""
    leaves: list[SurveyConditionLeaf] = []

    def visit(node: object, depth: int) -> None:
        if depth > 8 or type(node) is not dict or not node:
            raise SurveyConditionRuleError("invalid condition node")
        keys = set(node)
        group = keys & _GROUPS
        if group:
            if len(group) != 1 or len(keys) != 1:
                raise SurveyConditionRuleError("invalid condition group")
            children = node[next(iter(group))]
            if type(children) is not list or not 1 <= len(children) <= 20:
                raise SurveyConditionRuleError("invalid condition children")
            for child in children:
                visit(child, depth + 1)
            return
        if not keys <= {"question_ref", "operator", "value"}:
            raise SurveyConditionRuleError("unknown condition field")
        if type(node.get("question_ref")) is not str:
            raise SurveyConditionRuleError("invalid question reference")
        try:
            question_ref = uuid.UUID(node["question_ref"])
        except (ValueError, AttributeError):
            raise SurveyConditionRuleError("invalid question reference") from None
        operator = node.get("operator")
        if question_ref.int == 0 or type(operator) is not str:
            raise SurveyConditionRuleError("invalid condition leaf")
        has_value = "value" in node
        if operator in _VALUE_OPERATORS:
            if not has_value or not _valid_value(node["value"], operator):
                raise SurveyConditionRuleError("invalid condition value")
            leaf = SurveyConditionLeaf(question_ref, operator, node["value"])
        elif operator in _UNARY_OPERATORS:
            if has_value:
                raise SurveyConditionRuleError("unary condition cannot have a value")
            leaf = SurveyConditionLeaf(question_ref, operator)
        else:
            raise SurveyConditionRuleError("unsupported condition operator")
        leaves.append(leaf)
        if len(leaves) > 100:
            raise SurveyConditionRuleError("too many condition leaves")

    visit(rule, 1)
    return tuple(leaves)


def evaluate_condition_rule(
    rule: object, answers: Mapping[uuid.UUID, object],
) -> bool:
    """Evaluate a validated V1 rule against earlier active current answers."""
    if not isinstance(answers, Mapping):
        raise SurveyConditionRuleError("invalid answer mapping")
    parse_condition_rule(rule)

    def visit(node: dict) -> bool:
        if "all" in node:
            return all(visit(child) for child in node["all"])
        if "any" in node:
            return any(visit(child) for child in node["any"])
        reference = uuid.UUID(node["question_ref"])
        operator = node["operator"]
        present = reference in answers
        if operator == "ANSWERED":
            return present
        if operator == "NOT_ANSWERED":
            return not present
        if not present:
            return False
        answer, expected = answers[reference], node["value"]
        if operator in {"IN", "NOT_IN"}:
            matched = _answer_in(answer, expected)
        else:
            matched = _answer_equals(answer, expected)
        return not matched if operator in {"NOT_EQUALS", "NOT_IN"} else matched

    return visit(rule)


def _answer_equals(answer: object, expected: object) -> bool:
    if type(answer) is list:
        return any(type(item) is type(expected) and item == expected for item in answer)
    return type(answer) is type(expected) and answer == expected


def _answer_in(answer: object, expected: list[object]) -> bool:
    values = answer if type(answer) is list else [answer]
    return any(type(value) is type(item) and value == item
               for value in values for item in expected)


def _valid_value(value: object, operator: str) -> bool:
    if operator in {"IN", "NOT_IN"}:
        if type(value) is not list or not 1 <= len(value) <= 100:
            return False
        return all(_valid_scalar(item) for item in value) and len({
            (type(item).__name__, repr(item)) for item in value
        }) == len(value)
    return _valid_scalar(value)


def _valid_scalar(value: object) -> bool:
    if value is None or type(value) is bool:
        return True
    if type(value) is int:
        return -(2 ** 53) <= value <= 2 ** 53
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is str:
        return len(value) <= 2000
    return False
