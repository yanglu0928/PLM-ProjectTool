"""Pure current-answer completeness rules for Survey Assignment SUBMIT."""

from __future__ import annotations

import math
import uuid
from datetime import date
from pathlib import PurePath

from .condition_rules import SurveyConditionRuleError, evaluate_condition_rule
from .submission_views import (
    CurrentSubmissionAnswer, SubmissionCompletenessReport, SubmissionQuestion,
    SurveyAssignmentSubmissionSnapshot,
)


class SurveySubmissionIncomplete(ValueError):
    pass


def evaluate_submission(
    snapshot: SurveyAssignmentSubmissionSnapshot,
    evidence_names: dict[uuid.UUID, str],
) -> SubmissionCompletenessReport:
    if (type(snapshot) is not SurveyAssignmentSubmissionSnapshot
            or type(evidence_names) is not dict):
        raise SurveySubmissionIncomplete()
    current = {answer.question_row_id: answer for answer in snapshot.answers}
    if len(current) != len(snapshot.answers):
        raise SurveySubmissionIncomplete()
    active_values: dict[uuid.UUID, object] = {}
    active = answered = evidence_total = 0
    for question in snapshot.questions:
        if type(question) is not SubmissionQuestion:
            raise SurveySubmissionIncomplete()
        try:
            enabled = (question.condition_rule is None
                       or evaluate_condition_rule(
                           question.condition_rule, active_values))
        except SurveyConditionRuleError:
            raise SurveySubmissionIncomplete() from None
        answer = current.get(question.question_row_id)
        if not enabled:
            continue
        active += 1
        if answer is None:
            if question.required:
                raise SurveySubmissionIncomplete()
            continue
        _validate_answer(question, answer, evidence_names)
        active_values[question.question_id] = answer.answer_value
        answered += 1
        evidence_total += len(answer.evidence)
    return SubmissionCompletenessReport(active, answered, evidence_total)


def _validate_answer(question: SubmissionQuestion, answer: CurrentSubmissionAnswer,
                     names: dict[uuid.UUID, str]) -> None:
    evidence_ids = tuple(item.evidence_id for item in answer.evidence)
    if (question.evidence_required and not evidence_ids
            or answer.response_source == "FACILITATED_RECORD"
            and answer.source_evidence_id not in evidence_ids):
        raise SurveySubmissionIncomplete()
    value, rule = answer.answer_value, question.validation_rule
    if question.answer_type == "TEXT":
        if type(value) is not str or not rule.get("min_length", 0) <= len(value) <= rule.get("max_length", 4000):
            raise SurveySubmissionIncomplete()
    elif question.answer_type == "SINGLE_CHOICE":
        if type(value) is not str or value not in question.option_codes:
            raise SurveySubmissionIncomplete()
    elif question.answer_type == "MULTIPLE_CHOICE":
        if (type(value) is not list or not value
                or len(set(value)) != len(value)
                or any(type(item) is not str or item not in question.option_codes for item in value)
                or not rule.get("min_selections", 0) <= len(value) <= rule.get(
                    "max_selections", len(question.option_codes))):
            raise SurveySubmissionIncomplete()
    elif question.answer_type == "DATE":
        try:
            parsed = date.fromisoformat(value) if type(value) is str else None
            minimum = None if rule.get("minimum") is None else date.fromisoformat(rule["minimum"])
            maximum = None if rule.get("maximum") is None else date.fromisoformat(rule["maximum"])
        except (TypeError, ValueError):
            raise SurveySubmissionIncomplete() from None
        if (parsed is None or minimum is not None and parsed < minimum
                or maximum is not None and parsed > maximum):
            raise SurveySubmissionIncomplete()
    elif question.answer_type == "NUMBER":
        if (type(value) not in (int, float)
                or type(value) is float and not math.isfinite(value)
                or rule.get("integer", False) and type(value) is not int
                or rule.get("minimum") is not None and value < rule["minimum"]
                or rule.get("maximum") is not None and value > rule["maximum"]):
            raise SurveySubmissionIncomplete()
    elif question.answer_type == "ATTACHMENT":
        if (type(value) is not list
                or value != [str(item) for item in evidence_ids]
                or not rule.get("min_files", 0) <= len(evidence_ids) <= rule.get("max_files", 20)):
            raise SurveySubmissionIncomplete()
        allowed = set(rule.get("allowed_extensions", []))
        if allowed and any(
                type(names.get(item)) is not str
                or PurePath(names[item]).suffix.lower() not in allowed
                for item in evidence_ids):
            raise SurveySubmissionIncomplete()
    else:
        raise SurveySubmissionIncomplete()
