"""SRV-01/SRV-02 project Survey identity and immutable definition schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer,
    LargeBinary, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
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


class SurveyRoundRow(Base):
    __tablename__ = "srv_rounds"
    __table_args__ = (
        UniqueConstraint("survey_round_id", "survey_version_id", "survey_id",
                         "project_id", name="uq_srv_rounds__identity"),
        UniqueConstraint("survey_id", "round_no", name="uq_srv_rounds__survey_no"),
        ForeignKeyConstraint(
            ["survey_version_id", "survey_id", "project_id"],
            ["plm.srv_survey_versions.survey_version_id",
             "plm.srv_survey_versions.survey_id",
             "plm.srv_survey_versions.project_id"],
            name="fk_srv_rounds__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_rounds__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_rounds__updater", ondelete="NO ACTION"),
        ForeignKeyConstraint(["opened_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_rounds__opener", ondelete="NO ACTION"),
        ForeignKeyConstraint(["closed_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_rounds__closer", ondelete="NO ACTION"),
        ForeignKeyConstraint(["cancelled_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_rounds__canceller", ondelete="NO ACTION"),
        CheckConstraint("round_no>0", name="ck_srv_rounds__number"),
        CheckConstraint("round_state IN ('PLANNED','OPEN','CLOSED','CANCELLED')",
                        name="ck_srv_rounds__state"),
        CheckConstraint(
            "(scheduled_start_at IS NULL AND scheduled_end_at IS NULL) OR "
            "(scheduled_start_at IS NOT NULL AND scheduled_end_at IS NOT NULL "
            "AND scheduled_end_at>scheduled_start_at)",
            name="ck_srv_rounds__schedule",
        ),
        CheckConstraint(
            "location_note IS NULL OR (char_length(location_note) BETWEEN 1 AND 1000 "
            "AND location_note=btrim(location_note))",
            name="ck_srv_rounds__location",
        ),
        CheckConstraint(
            "(round_state='PLANNED' AND opened_by IS NULL AND opened_at IS NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NULL "
            "AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(round_state='OPEN' AND opened_by IS NOT NULL AND opened_at IS NOT NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NULL "
            "AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(round_state='CLOSED' AND opened_by IS NOT NULL AND opened_at IS NOT NULL "
            "AND closed_by IS NOT NULL AND closed_at IS NOT NULL "
            "AND close_report_fingerprint IS NOT NULL "
            "AND octet_length(close_report_fingerprint)=32 "
            "AND cancelled_by IS NULL AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL AND closed_at>=opened_at) OR "
            "(round_state='CANCELLED' AND opened_by IS NULL AND opened_at IS NULL "
            "AND closed_by IS NULL AND closed_at IS NULL "
            "AND close_report_fingerprint IS NULL AND cancelled_by IS NOT NULL "
            "AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL "
            "AND char_length(cancellation_reason) BETWEEN 1 AND 2000 "
            "AND cancellation_reason=btrim(cancellation_reason) "
            "AND cancelled_at>=created_at)",
            name="ck_srv_rounds__lifecycle",
        ),
        CheckConstraint("lock_version>=0", name="ck_srv_rounds__lock"),
        Index("ix_srv_rounds__project_state_schedule", "project_id", "round_state",
              "scheduled_start_at", "survey_round_id"),
        Index("ix_srv_rounds__survey_number", "survey_id", "round_no"),
        {"schema": "plm"},
    )

    survey_round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    round_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'PLANNED'"),
    )
    scheduled_start_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
    )
    scheduled_end_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
    )
    location_note: Mapped[str | None] = mapped_column(Text)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    opened_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    close_report_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
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


class SurveyRoundSourceRecordRow(Base):
    __tablename__ = "srv_round_source_records"
    __table_args__ = (
        UniqueConstraint("survey_round_id", "ordinal",
                         name="uq_srv_round_sources__round_ordinal"),
        UniqueConstraint("survey_round_id", "question_row_id", "evidence_id",
                         name="uq_srv_round_sources__round_question_evidence",
                         postgresql_nulls_not_distinct=True),
        ForeignKeyConstraint(
            ["survey_round_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_rounds.survey_round_id", "plm.srv_rounds.survey_version_id",
             "plm.srv_rounds.survey_id", "plm.srv_rounds.project_id"],
            name="fk_srv_round_sources__round", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"],
            name="fk_srv_round_sources__question", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_round_sources__document", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_srv_round_sources__evidence", ondelete="NO ACTION"),
        ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_round_sources__recorder", ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_srv_round_sources__ordinal"),
        CheckConstraint("observed_evidence_lock_version>=0",
                        name="ck_srv_round_sources__evidence_lock"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_srv_round_sources__fingerprint"),
        CheckConstraint("recorded_at<=created_at", name="ck_srv_round_sources__recorded_at"),
        Index("ix_srv_round_sources__evidence", "evidence_id", "survey_round_id"),
        Index("ix_srv_round_sources__question", "question_row_id", "survey_round_id"),
        {"schema": "plm"},
    )

    round_source_record_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_evidence_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyAssignmentRow(Base):
    __tablename__ = "srv_assignments"
    __table_args__ = (
        UniqueConstraint(
            "survey_assignment_id", "survey_round_id", "survey_version_id",
            "survey_id", "project_id", name="uq_srv_assignments__identity",
        ),
        UniqueConstraint(
            "survey_round_id", "department_id", "assignee_user_id",
            name="uq_srv_assignments__round_target",
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["survey_round_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_rounds.survey_round_id",
             "plm.srv_rounds.survey_version_id", "plm.srv_rounds.survey_id",
             "plm.srv_rounds.project_id"],
            name="fk_srv_assignments__round", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["survey_version_id", "department_id"],
            ["plm.srv_target_departments.survey_version_id",
             "plm.srv_target_departments.department_id"],
            name="fk_srv_assignments__target", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_assignments__department", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["assignee_user_id"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__assignee",
                             ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__updater", ondelete="NO ACTION"),
        ForeignKeyConstraint(["submitted_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__submitter", ondelete="NO ACTION"),
        ForeignKeyConstraint(["validated_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__validator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["returned_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_assignments__returner", ondelete="NO ACTION"),
        CheckConstraint(
            "submission_state IN ('ASSIGNED','IN_PROGRESS','SUBMITTED',"
            "'VALIDATED','RETURNED')", name="ck_srv_assignments__state",
        ),
        CheckConstraint(
            "return_comment IS NULL OR (char_length(return_comment) BETWEEN 1 AND 2000 "
            "AND return_comment=btrim(return_comment))",
            name="ck_srv_assignments__return_comment",
        ),
        CheckConstraint("lock_version>=0", name="ck_srv_assignments__lock"),
        Index("ix_srv_assignments__round_state", "survey_round_id",
              "submission_state", "survey_assignment_id"),
        Index("ix_srv_assignments__assignee_state", "assignee_user_id",
              "submission_state", "survey_assignment_id"),
        {"schema": "plm"},
    )

    survey_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submission_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ASSIGNED'"),
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    validated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    validated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    returned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    returned_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    return_comment: Mapped[str | None] = mapped_column(Text)
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


class SurveyResponseRow(Base):
    __tablename__ = "srv_responses"
    __table_args__ = (
        UniqueConstraint(
            "survey_response_id", "survey_assignment_id", "question_row_id",
            "project_id", name="uq_srv_responses__identity",
        ),
        UniqueConstraint(
            "survey_assignment_id", "question_row_id", "correction_of_response_id",
            name="uq_srv_responses__question_chain",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("correction_of_response_id",
                         name="uq_srv_responses__correction_successor"),
        ForeignKeyConstraint(
            ["survey_assignment_id", "survey_round_id", "survey_version_id",
             "survey_id", "project_id"],
            ["plm.srv_assignments.survey_assignment_id",
             "plm.srv_assignments.survey_round_id",
             "plm.srv_assignments.survey_version_id",
             "plm.srv_assignments.survey_id", "plm.srv_assignments.project_id"],
            name="fk_srv_responses__assignment", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["question_row_id", "survey_version_id", "survey_id", "project_id"],
            ["plm.srv_questions.question_row_id",
             "plm.srv_questions.survey_version_id", "plm.srv_questions.survey_id",
             "plm.srv_questions.project_id"],
            name="fk_srv_responses__question", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["correction_of_response_id"],
                             ["plm.srv_responses.survey_response_id"],
                             name="fk_srv_responses__correction", ondelete="NO ACTION"),
        ForeignKeyConstraint(["round_source_record_ref_id"],
                             ["plm.srv_round_source_records.round_source_record_ref_id"],
                             name="fk_srv_responses__round_source", ondelete="NO ACTION"),
        ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_responses__recorder", ondelete="NO ACTION"),
        CheckConstraint(
            "response_source IN ('SELF_SERVICE','FACILITATED_RECORD')",
            name="ck_srv_responses__source",
        ),
        CheckConstraint(
            "(response_source='SELF_SERVICE' AND round_source_record_ref_id IS NULL) OR "
            "(response_source='FACILITATED_RECORD' AND "
            "round_source_record_ref_id IS NOT NULL)",
            name="ck_srv_responses__source_shape",
        ),
        CheckConstraint("recorded_at<=created_at", name="ck_srv_responses__recorded_at"),
        Index("ix_srv_responses__assignment_recorded", "survey_assignment_id",
              "recorded_at", "survey_response_id"),
        Index("ix_srv_responses__question", "question_row_id", "survey_response_id"),
        {"schema": "plm"},
    )

    survey_response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    response_source: Mapped[str] = mapped_column(Text, nullable=False)
    round_source_record_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    correction_of_response_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyAnswerRow(Base):
    __tablename__ = "srv_answers"
    __table_args__ = (
        UniqueConstraint("survey_response_id", name="uq_srv_answers__response"),
        UniqueConstraint(
            "survey_answer_id", "survey_response_id", "survey_assignment_id",
            "question_row_id", "project_id", name="uq_srv_answers__identity",
        ),
        ForeignKeyConstraint(
            ["survey_response_id", "survey_assignment_id", "question_row_id",
             "project_id"],
            ["plm.srv_responses.survey_response_id",
             "plm.srv_responses.survey_assignment_id",
             "plm.srv_responses.question_row_id", "plm.srv_responses.project_id"],
            name="fk_srv_answers__response", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "raw_answer IS NOT NULL OR answer_value IS NOT NULL",
            name="ck_srv_answers__value",
        ),
        CheckConstraint(
            "raw_answer IS NULL OR (char_length(raw_answer) BETWEEN 1 AND 20000 "
            "AND raw_answer=btrim(raw_answer))",
            name="ck_srv_answers__raw",
        ),
        {"schema": "plm"},
    )

    survey_answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_response_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    raw_answer: Mapped[str | None] = mapped_column(Text)
    answer_value: Mapped[object | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyAnswerEvidenceRefRow(Base):
    __tablename__ = "srv_answer_evidence_refs"
    __table_args__ = (
        UniqueConstraint("survey_answer_id", "ordinal",
                         name="uq_srv_answer_evidence__answer_ordinal"),
        UniqueConstraint("survey_answer_id", "evidence_id",
                         name="uq_srv_answer_evidence__answer_evidence"),
        ForeignKeyConstraint(
            ["survey_answer_id", "survey_response_id", "survey_assignment_id",
             "question_row_id", "project_id"],
            ["plm.srv_answers.survey_answer_id",
             "plm.srv_answers.survey_response_id",
             "plm.srv_answers.survey_assignment_id",
             "plm.srv_answers.question_row_id", "plm.srv_answers.project_id"],
            name="fk_srv_answer_evidence__answer", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_answer_evidence__document", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_srv_answer_evidence__evidence",
                             ondelete="NO ACTION"),
        ForeignKeyConstraint(["recorded_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_answer_evidence__recorder",
                             ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_srv_answer_evidence__ordinal"),
        CheckConstraint("observed_evidence_lock_version>=0",
                        name="ck_srv_answer_evidence__lock"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_srv_answer_evidence__fingerprint"),
        CheckConstraint("recorded_at<=created_at",
                        name="ck_srv_answer_evidence__recorded_at"),
        Index("ix_srv_answer_evidence__evidence", "evidence_id", "survey_answer_id"),
        {"schema": "plm"},
    )

    survey_answer_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_answer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_response_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_evidence_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyConclusionRow(Base):
    __tablename__ = "srv_conclusions"
    __table_args__ = (
        UniqueConstraint(
            "survey_conclusion_id", "conclusion_series_id", "project_id",
            name="uq_srv_conclusions__identity",
        ),
        UniqueConstraint("conclusion_series_id", "version_no",
                         name="uq_srv_conclusions__series_no"),
        ForeignKeyConstraint(
            ["survey_id", "project_id"],
            ["plm.srv_surveys.survey_id", "plm.srv_surveys.project_id"],
            name="fk_srv_conclusions__survey", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["supersedes_ref", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusions__supersedes", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_srv_conclusions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"],
                             ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_srv_conclusions__review_round",
                             ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_srv_conclusions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_srv_conclusions__number"),
        CheckConstraint(
            "conclusion_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_srv_conclusions__state",
        ),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_srv_conclusions__fingerprint"),
        CheckConstraint(
            "cardinality(round_refs)>0 AND array_position(round_refs,NULL) IS NULL "
            "AND array_position(ai_task_refs,NULL) IS NULL",
            name="ck_srv_conclusions__refs",
        ),
        CheckConstraint(
            "declared_department_count>=0 AND declared_module_count>=0 "
            "AND declared_department_count+declared_module_count>0 "
            "AND declared_evidence_count>0 AND declared_open_issue_count>=0",
            name="ck_srv_conclusions__counts",
        ),
        CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_srv_conclusions__review_shape",
        ),
        Index("ix_srv_conclusions__project_created", "project_id", "created_at",
              "survey_conclusion_id"),
        Index("ix_srv_conclusions__series_version", "project_id",
              "conclusion_series_id", "version_no"),
        Index("uq_srv_conclusions__series_in_review", "conclusion_series_id",
              unique=True, postgresql_where=text("conclusion_state='IN_REVIEW'")),
        Index("uq_srv_conclusions__series_approved", "conclusion_series_id",
              unique=True, postgresql_where=text("conclusion_state='APPROVED'")),
        {"schema": "plm"},
    )

    survey_conclusion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    conclusion_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    survey_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    round_refs: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    ai_task_refs: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]"),
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    conclusion_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'DRAFT'"),
    )
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    declared_department_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_module_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_open_issue_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyDepartmentConclusionRow(Base):
    __tablename__ = "srv_department_conclusions"
    __table_args__ = (
        UniqueConstraint("survey_conclusion_id", "ordinal",
                         name="uq_srv_department_conclusions__ordinal"),
        UniqueConstraint("survey_conclusion_id", "department_id",
                         name="uq_srv_department_conclusions__department"),
        ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_department_conclusions__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["department_id", "project_id"],
            ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
            name="fk_srv_department_conclusions__department", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["decision_evidence_id"],
                             ["plm.evd_evidence_records.evidence_id"],
                             name="fk_srv_department_conclusions__decision_evidence",
                             ondelete="NO ACTION"),
        ForeignKeyConstraint(["decision_review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_srv_department_conclusions__decision_review",
                             ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_srv_department_conclusions__ordinal"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                        name="ck_srv_department_conclusions__title"),
        CheckConstraint("char_length(statement) BETWEEN 1 AND 20000 "
                        "AND statement=btrim(statement)",
                        name="ck_srv_department_conclusions__statement"),
        CheckConstraint("array_position(response_refs,NULL) IS NULL",
                        name="ck_srv_department_conclusions__responses"),
        CheckConstraint(
            "(decision_type IS NULL AND decision_reason IS NULL "
            "AND decision_impact IS NULL AND decision_evidence_id IS NULL "
            "AND decision_review_ref IS NULL) OR "
            "(decision_type IN ('SCOPE_EXCLUSION','RISK_ACCEPTANCE') "
            "AND char_length(decision_reason) BETWEEN 1 AND 2000 "
            "AND decision_reason=btrim(decision_reason) "
            "AND char_length(decision_impact) BETWEEN 1 AND 2000 "
            "AND decision_impact=btrim(decision_impact) "
            "AND decision_evidence_id IS NOT NULL AND decision_review_ref IS NOT NULL)",
            name="ck_srv_department_conclusions__decision",
        ),
        {"schema": "plm"},
    )

    department_conclusion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_conclusion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conclusion_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    response_refs: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]"),
    )
    decision_type: Mapped[str | None] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decision_impact: Mapped[str | None] = mapped_column(Text)
    decision_evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decision_review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyModuleConclusionRow(Base):
    __tablename__ = "srv_module_conclusions"
    __table_args__ = (
        UniqueConstraint("survey_conclusion_id", "ordinal",
                         name="uq_srv_module_conclusions__ordinal"),
        UniqueConstraint("survey_conclusion_id", "module_key",
                         name="uq_srv_module_conclusions__key"),
        ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_module_conclusions__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["decision_evidence_id"],
                             ["plm.evd_evidence_records.evidence_id"],
                             name="fk_srv_module_conclusions__decision_evidence",
                             ondelete="NO ACTION"),
        ForeignKeyConstraint(["decision_review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_srv_module_conclusions__decision_review",
                             ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_srv_module_conclusions__ordinal"),
        CheckConstraint("module_key ~ '^[A-Z][A-Z0-9_.-]{0,63}$'",
                        name="ck_srv_module_conclusions__key"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                        name="ck_srv_module_conclusions__title"),
        CheckConstraint("char_length(statement) BETWEEN 1 AND 20000 "
                        "AND statement=btrim(statement)",
                        name="ck_srv_module_conclusions__statement"),
        CheckConstraint("array_position(response_refs,NULL) IS NULL",
                        name="ck_srv_module_conclusions__responses"),
        CheckConstraint(
            "(decision_type IS NULL AND decision_reason IS NULL "
            "AND decision_impact IS NULL AND decision_evidence_id IS NULL "
            "AND decision_review_ref IS NULL) OR "
            "(decision_type IN ('SCOPE_EXCLUSION','RISK_ACCEPTANCE') "
            "AND char_length(decision_reason) BETWEEN 1 AND 2000 "
            "AND decision_reason=btrim(decision_reason) "
            "AND char_length(decision_impact) BETWEEN 1 AND 2000 "
            "AND decision_impact=btrim(decision_impact) "
            "AND decision_evidence_id IS NOT NULL AND decision_review_ref IS NOT NULL)",
            name="ck_srv_module_conclusions__decision",
        ),
        {"schema": "plm"},
    )

    module_conclusion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_conclusion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conclusion_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    module_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    response_refs: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]"),
    )
    decision_type: Mapped[str | None] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decision_impact: Mapped[str | None] = mapped_column(Text)
    decision_evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decision_review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyConclusionEvidenceRefRow(Base):
    __tablename__ = "srv_conclusion_evidence_refs"
    __table_args__ = (
        UniqueConstraint("survey_conclusion_id", "ordinal",
                         name="uq_srv_conclusion_evidence__ordinal"),
        UniqueConstraint("survey_conclusion_id", "evidence_id", "reference_role",
                         name="uq_srv_conclusion_evidence__role"),
        ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusion_evidence__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_srv_conclusion_evidence__document", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_srv_conclusion_evidence__evidence",
                             ondelete="NO ACTION"),
        CheckConstraint("reference_role IN ('SUPPORT','CONFLICT')",
                        name="ck_srv_conclusion_evidence__role"),
        CheckConstraint("observed_evidence_lock_version>=0",
                        name="ck_srv_conclusion_evidence__lock"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_srv_conclusion_evidence__fingerprint"),
        CheckConstraint("ordinal>=0", name="ck_srv_conclusion_evidence__ordinal"),
        Index("ix_srv_conclusion_evidence__evidence", "evidence_id",
              "survey_conclusion_id"),
        {"schema": "plm"},
    )

    conclusion_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_conclusion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conclusion_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reference_role: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_evidence_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class SurveyConclusionOpenIssueRow(Base):
    __tablename__ = "srv_conclusion_open_issues"
    __table_args__ = (
        UniqueConstraint("survey_conclusion_id", "ordinal",
                         name="uq_srv_conclusion_issues__ordinal"),
        UniqueConstraint("survey_conclusion_id", "issue_owner_module",
                         "issue_object_type", "issue_id",
                         name="uq_srv_conclusion_issues__issue"),
        ForeignKeyConstraint(
            ["survey_conclusion_id", "conclusion_series_id", "project_id"],
            ["plm.srv_conclusions.survey_conclusion_id",
             "plm.srv_conclusions.conclusion_series_id",
             "plm.srv_conclusions.project_id"],
            name="fk_srv_conclusion_issues__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["issue_id", "project_id"],
            ["plm.hnd_action_items.action_item_id", "plm.hnd_action_items.project_id"],
            name="fk_srv_conclusion_issues__handover_action", ondelete="NO ACTION",
        ),
        CheckConstraint("issue_owner_module='handover' AND issue_object_type='HND-03'",
                        name="ck_srv_conclusion_issues__type"),
        CheckConstraint(
            "observed_issue_state IN ('OPEN','IN_PROGRESS','SUBMITTED','VERIFIED',"
            "'CLOSED','CANCELLED')", name="ck_srv_conclusion_issues__state",
        ),
        CheckConstraint("observed_lock_version>=0",
                        name="ck_srv_conclusion_issues__lock"),
        CheckConstraint("ordinal>=0", name="ck_srv_conclusion_issues__ordinal"),
        Index("ix_srv_conclusion_issues__issue", "issue_id",
              "survey_conclusion_id"),
        {"schema": "plm"},
    )

    conclusion_open_issue_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    survey_conclusion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conclusion_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issue_owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    issue_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_issue_state: Mapped[str] = mapped_column(Text, nullable=False)
    observed_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
