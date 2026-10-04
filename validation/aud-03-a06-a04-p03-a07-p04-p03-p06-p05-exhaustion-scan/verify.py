"""Actual non-locking candidate + safe one-candidate sweep, no process loop."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.audit.application.sweep_exhausted_export import AuditExportExhaustionSweep
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutionOutcome
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCandidates
from plm_assistant.modules.jobs.infrastructure.audit_export_exhaustion_scan_repository import SqlAlchemyAuditExportExhaustionScanRepository

spec=spec_from_file_location('_scan_exhaustion_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a07-p04-p03-p06-p04-exhaustion'/'verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)


def exercise(v):
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def decorate(executor,fd):
        sweep=AuditExportExhaustionSweep(unit_of_work=fd['unit_of_work'],candidates=AuditExportExhaustionCandidates(repository=SqlAlchemyAuditExportExhaustionScanRepository()),
            system_actor=fd['system_actor'],exhaustion=executor._exhaustion)
        before=snapshot();assert sweep.peek_next() is None and sweep.run_next() is None and snapshot()==before
        class SweptExecutor:
            def execute(self,c):
                before=snapshot();candidate=sweep.peek_next();assert snapshot()==before
                if candidate is None:return executor.execute(c)
                assert (candidate.job_id,candidate.export_id,candidate.fencing_token,candidate.worker_ref)==(c.job_id,c.export_id,c.fencing_token,c.worker_ref)
                receipt=sweep.run_next();result=AuditExportExecutionOutcome(c,'FAILED',receipt)
                before=snapshot();assert sweep.peek_next() is None and sweep.run_next() is None and snapshot()==before
                return result
        return SweptExecutor()
    p.exercise(v,decorate_executor=decorate)
    print('P06-P05 PASS: actual PG dualScope one exhausted-expired candidate/current Worker-fence-original export; six-table readonly scanning and no candidates after controlled failure; actual safe owner true commit-lost-ack recovery. Earlier attempts/alive/stale/rollback/User-License denial and old bytes retained via real P04 fixture. Concurrent sweeping/fair scheduling/quarantine/loop/production/package NOT proved.')


if __name__=='__main__':p.fixture.main(exercise=exercise)
