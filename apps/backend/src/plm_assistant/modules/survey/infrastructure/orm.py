"""SRV-01/SRV-02 project Survey identity and immutable definition schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer,
    LargeBinary, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class SurveyRow(Base):
    __tablename__ = "srv_surveys"
    __table_args__ = (
        UniqueConstraint("survey_id", "project_id",
                         name="uq_srv_surveys__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_srv_surveys__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_surveys__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_surveys__updater", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_surveys__approved_version", ondelete="NO ACTION",
            use_alter=True,
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_srv_surveys__name",
        ),
        CheckConstraint("survey_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                        name="ck_srv_surveys__state"),
        CheckConstraint("lock_version>=0", name="ck_srv_surveys__lock"),
        Index("ix_srv_surveys__project_state", "project_id", "survey_state",
              "survey_id"),
        {"schema": "plm"},
    )

    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    survey_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'"),
    )
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"),
    )


class SurveyVersionRow(Base):
    __tablename__ = "srv_survey_versions"
    __table_args__ = (
        UniqueConstraint("survey_version_id", "survey_id", "project_id",
                         name="uq_srv_versions__id_survey_project"),
        UniqueConstraint("survey_id", "version_no",
                         name="uq_srv_versions__survey_no"),
        ForeignKeyConstraint(
            ["survey_id", "project_id"],
            ["plm.srv_surveys.survey_id", "plm.srv_surveys.project_id"],
            name="fk_srv_versions__survey", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_ref", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_versions__supersedes", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_srv_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"],
                             ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_srv_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_srv_versions__number"),
        CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_srv_versions__state",
        ),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_srv_versions__fingerprint"),
        CheckConstraint(
            "declared_question_count>0 AND declared_option_count>=0 "
            "AND declared_source_count>=declared_question_count "
            "AND declared_target_department_count>0",
            name="ck_srv_versions__counts",
        ),
        CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_srv_versions__review_shape",
        ),
        Index("ix_srv_versions__survey_created", "survey_id", "created_at"),
        Index("uq_srv_versions__survey_in_review", "survey_id", unique=True,
              postgresql_where=text("version_state='IN_REVIEW'")),
        Index("uq_srv_versions__survey_approved", "survey_id", unique=True,
              postgresql_where=text("version_state='APPROVED'")),
        {"schema": "plm"},
    )

    survey_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'DRAFT'"),
    )
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    declared_question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_option_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_target_department_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyQuestionRow(Base):
    __tablename__ = "srv_questions"
    __table_args__ = (
        UniqueConstraint("question_row_id", "survey_version_id", "survey_id",
                         "project_id", name="uq_srv_questions__row_version_survey_project"),
        UniqueConstraint("survey_version_id", "question_id",
                         name="uq_srv_questions__version_stable"),
        UniqueConstraint("survey_version_id", "sequence_no",
                         name="uq_srv_questions__version_sequence"),
        ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_questions__version", ondelete="NO ACTION",
        ),
        CheckConstraint("sequence_no>=0", name="ck_srv_questions__sequence"),
        CheckConstraint(
            "char_length(topic) BETWEEN 1 AND 255 AND topic=btrim(topic) "
            "AND char_length(question_text) BETWEEN 1 AND 4000 "
            "AND question_text=btrim(question_text) "
            "AND char_length(objective) BETWEEN 1 AND 2000 "
            "AND objective=btrim(objective) "
            "AND char_length(expected_output) BETWEEN 1 AND 2000 "
            "AND expected_output=btrim(expected_output)",
            name="ck_srv_questions__texts",
        ),
        CheckConstraint(
            "answer_type IN ('TEXT','SINGLE_CHOICE','MULTIPLE_CHOICE','DATE',"
            "'NUMBER','ATTACHMENT')", name="ck_srv_questions__answer_type",
        ),
        CheckConstraint("jsonb_typeof(validation_rule)='object'",
                        name="ck_srv_questions__validation"),
        CheckConstraint(
            "condition_rule IS NULL OR jsonb_typeof(condition_rule)='object'",
            name="ck_srv_questions__condition",
        ),
        Index("ix_srv_questions__version_sequence", "survey_version_id", "sequence_no"),
        {"schema": "plm"},
    )

    question_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(Text, nullable=False)
    validation_rule: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    condition_rule: Mapped[dict | None] = mapped_column(JSONB)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )


class SurveyQuestionOptionRow(Base):
    __tablename__ = "srv_question_options"
    __table_args__ = (
        UniqueConstraint("question_row_id", "option_code",
                         name="uq_srv_options__question_code"),
        UniqueConstraint("question_row_id", "ordinal",
                         name="uq_srv_options__question_ordinal"),
        ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id",
             "plm.srv_questions.survey_id", "plm.srv_questions.project_id"],
            name="fk_srv_options__question", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_srv_options__ordinal"),
        CheckConstraint("option_code ~ '^[A-Z][A-Z0-9_-]{0,31}$'",
                        name="ck_srv_options__code"),
        CheckConstraint(
            "char_length(label) BETWEEN 1 AND 255 AND label=btrim(label) "
            "AND (description IS NULL OR (char_length(description) BETWEEN 1 AND 1000 "
            "AND description=btrim(description)))",
            name="ck_srv_options__texts",
        ),
        {"schema": "plm"},
    )

    question_option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    question_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    option_code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class SurveyQuestionSourceRefRow(Base):
    __tablename__ = "srv_question_source_refs"
    __table_args__ = (
        UniqueConstraint("question_row_id", "ordinal",
                         name="uq_srv_question_sources__question_ordinal"),
        ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id",
             "plm.srv_questions.survey_id", "plm.srv_questions.project_id"],
            name="fk_srv_question_sources__question", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["handover_item_row_id", "handover_analysis_version_id",
             "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_items.analysis_item_row_id",
             "plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.handover_analysis_id",
             "plm.hnd_analysis_items.project_id"],
            name="fk_srv_question_sources__handover_item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["capability_item_row_id", "capability_baseline_version_id",
             "capability_baseline_id"],
            ["plm.cap_items.capability_item_row_id",
             "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"],
            name="fk_srv_question_sources__capability_item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["template_document_version_id", "template_document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_question_sources__template_version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_srv_question_sources__ordinal"),
        CheckConstraint(
            "(source_kind='HANDOVER_ITEM' AND handover_item_row_id IS NOT NULL "
            "AND handover_analysis_version_id IS NOT NULL "
            "AND handover_analysis_id IS NOT NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NULL) OR "
            "(source_kind='CAPABILITY_ITEM' AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NOT NULL "
            "AND capability_baseline_version_id IS NOT NULL "
            "AND capability_baseline_id IS NOT NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NULL) OR "
            "(source_kind='TEMPLATE_DOCUMENT_VERSION' "
            "AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NOT NULL "
            "AND template_document_id IS NOT NULL AND manual_source_note IS NULL) OR "
            "(source_kind='MANUAL' AND handover_item_row_id IS NULL "
            "AND handover_analysis_version_id IS NULL "
            "AND handover_analysis_id IS NULL "
            "AND capability_item_row_id IS NULL "
            "AND capability_baseline_version_id IS NULL "
            "AND capability_baseline_id IS NULL "
            "AND template_document_version_id IS NULL "
            "AND template_document_id IS NULL AND manual_source_note IS NOT NULL "
            "AND char_length(manual_source_note) BETWEEN 1 AND 2000 "
            "AND manual_source_note=btrim(manual_source_note))",
            name="ck_srv_question_sources__shape",
        ),
        Index("ix_srv_question_sources__handover", "handover_item_row_id"),
        Index("ix_srv_question_sources__capability", "capability_item_row_id"),
        Index("ix_srv_question_sources__template", "template_document_version_id"),
        {"schema": "plm"},
    )

    question_source_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    question_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    handover_item_row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    handover_analysis_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    handover_analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    capability_item_row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    capability_baseline_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    capability_baseline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    template_document_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    template_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    manual_source_note: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class SurveyTargetDepartmentRow(Base):
    __tablename__ = "srv_target_departments"
    __table_args__ = (
        UniqueConstraint("survey_version_id", "department_id",
                         name="uq_srv_targets__version_department"),
        UniqueConstraint("survey_version_id", "ordinal",
                         name="uq_srv_targets__version_ordinal"),
        ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_targets__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_targets__department", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_srv_targets__ordinal"),
        Index("ix_srv_targets__department", "department_id", "survey_version_id"),
        {"schema": "plm"},
    )

    survey_target_department_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
