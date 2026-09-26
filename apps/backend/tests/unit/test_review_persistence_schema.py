import importlib
import unittest
import sqlalchemy as sa
from plm_assistant.modules.review.infrastructure import orm


class ReviewPersistenceSchemaTests(unittest.TestCase):
    def test_exact_owned_tables_and_global_fk_nonnullable_generated_key(self):
        names = {t.name for t in orm._tables}
        self.assertEqual(names, {"rvw_reviews", "rvw_review_rounds", "rvw_review_assignments", "rvw_review_decisions",
                                "rvw_subject_snapshots", "rvw_subject_snapshot_refs", "rvw_subject_locks", "rvw_round_events"})
        for table in orm._tables:
            self.assertFalse(table.c.scope_project_key.nullable)
            self.assertTrue(table.c.scope_project_key.computed.persisted)
            for fk in table.foreign_key_constraints:
                self.assertEqual(fk.ondelete, "NO ACTION")
        active = next(fk for fk in orm.ReviewRow.__table__.foreign_key_constraints if fk.name == "fk_rvw_reviews__active_round")
        self.assertTrue(active.deferrable)
        self.assertEqual(active.initially, "DEFERRED")
        self.assertIn("scope_project_key", active.column_keys)

    def test_frozen_migration_factory_column_constraint_index_parity(self):
        module = importlib.import_module("plm_assistant.migrations.versions.20260926_0034_review_history")
        self.assertEqual(module.down_revision, "20260926_0033")
        metadata = sa.MetaData(naming_convention=orm.Base.metadata.naming_convention)
        tables = module._make_tables(lambda name, *args, **kwargs: sa.Table(name, metadata, *args, **kwargs))
        # Frozen 0034 stays unchanged; apply the explicit additive 0035 delta
        # to the expected schema rather than rewriting historical migrations.
        delta = importlib.import_module("plm_assistant.migrations.versions.20260926_0035_review_withdrawal_reason")
        self.assertEqual(delta.down_revision, module.revision)
        tables[-1].append_column(sa.Column("withdrawal_reason", sa.Text(), nullable=True))
        tables[-1].append_constraint(sa.CheckConstraint(delta._SHAPE, name=delta._CHECK))
        for old, runtime in zip(tables, orm._tables):
            self.assertEqual(set(old.c.keys()), set(runtime.c.keys()))
            self.assertEqual({c.name for c in old.constraints}, {c.name for c in runtime.constraints})
            self.assertEqual({i.name for i in old.indexes}, {i.name for i in runtime.indexes})

    def test_withdrawal_reason_nullable_text_and_offline_loss_guard(self):
        from unittest.mock import patch
        delta = importlib.import_module("plm_assistant.migrations.versions.20260926_0035_review_withdrawal_reason")
        self.assertTrue(orm.ReviewRoundEventRow.__table__.c.withdrawal_reason.nullable)
        self.assertIsInstance(orm.ReviewRoundEventRow.__table__.c.withdrawal_reason.type, sa.Text)
        with patch.object(delta.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline"): delta.downgrade()

    def test_active_identity_indexes_and_append_atomicity_guards(self):
        module = importlib.import_module("plm_assistant.migrations.versions.20260926_0034_review_history")
        for expected in ("Review complete-set state invalid", "Review Subject lock atomicity invalid", "Review events incomplete",
                         "Review immutable record", "Review reviewer set sealed", "Review Trace facts mismatch",
                         "rr.changed_xid<>txid_current()", "Review terminal event chronology invalid"):
            self.assertIn(expected, module._GUARDS)
        index = next(i for i in orm.ReviewSubjectLockRow.__table__.indexes if i.name == "uq_rvw_locks__active_subject")
        self.assertTrue(index.unique)
        self.assertEqual(tuple(c.name for c in index.columns), ("scope", "scope_project_key", "subject_type", "subject_id"))
