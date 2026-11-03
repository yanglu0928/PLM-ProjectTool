from __future__ import annotations
import copy
import hashlib
import unittest
import uuid
from datetime import datetime, timezone
from plm_assistant.modules.plugin.application.installation_owner import InstallablePluginPackage,PluginInstallationEvidence
from plm_assistant.modules.plugin.application.revalidation_owner import (
    PluginRuntimeRevalidationContext,PluginRuntimeRevalidationOwner,
    PluginRuntimeRevalidationOwnerError,RevalidatePluginInstallationCommand)

class _Repo:
    def __init__(self,state="ENABLED",compatible=True):
        self.installation_id=uuid.uuid4();self.package_id=uuid.uuid4()
        self.snapshot={"schema_version":"1","os":"windows-11","architecture":"x86_64",
                       "python_version":"3.13.15","dependency_versions":{"demo":"1.0"}}
        self.package=InstallablePluginPackage(self.package_id,"synthetic.echo",
            hashlib.sha256(b"package").digest(),{"schema_version":"plm.plugin.manifest.v1"})
        self.state=state;self.version=4
        self.latest_state="INCOMPATIBLE" if state=="INCOMPATIBLE" else "COMPATIBLE"
        self.latest_snapshot=copy.deepcopy(self.snapshot);self.compatible=compatible
        self.ops=("document.export","document.render") if state=="ENABLED" else ()
        self.history=[];self.authorized=False;self.applied=None;self.plugin="synthetic.echo"
    def identify_plugin(self,_tx,*,installation_id):
        return self.plugin if installation_id==self.installation_id else None
    def lock_plugin(self,_tx,*,plugin_id):self.locked=plugin_id
    def load_context(self,_tx,*,installation_id):
        if installation_id!=self.installation_id:return None
        return PluginRuntimeRevalidationContext(self.plugin,self.installation_id,self.package,
            "VERIFIED",self.state,self.version,copy.deepcopy(self.snapshot),self.latest_state,
            copy.deepcopy(self.latest_snapshot),self.ops)
    def apply_revalidation(self,_tx,*,context,compatibility_state,runtime_snapshot,
                           installation_state,actor_id,changed_at):
        self.authorized=True;self.applied=(compatibility_state,installation_state)
        self.snapshot=copy.deepcopy(runtime_snapshot);self.state=installation_state;self.version+=1
        if compatibility_state=="INCOMPATIBLE":self.ops=()
    def append_disabled_operation_history(self,_tx,*,installation_id,package_id,plugin_id,
        operation_id,actor_id,trace_id,audit_event_id):self.history.append(operation_id)

class _Evidence:
    def __init__(self,repo):self.repo=repo;self.calls=0;self.bad_hash=False;self.present=True
    def inspect_installed_package(self,package):
        self.calls+=1
        return PluginInstallationEvidence(package.plugin_package_id,
            b"x"*32 if self.bad_hash else package.package_sha256,self.present,
            self.repo.compatible,copy.deepcopy(self.repo.snapshot))

class _Audit:
    def __init__(self,fail=False):self.events=[];self.fail=fail
    def append(self,_tx,event):
        if self.fail:raise RuntimeError("synthetic audit unavailable")
        self.events.append(event);return uuid.uuid4()

class _Uow:
    def __init__(self,repo,audit):self.repo,self.audit=repo,audit;self.committed=False
    def __enter__(self):
        self.before=copy.deepcopy((self.repo.snapshot,self.repo.state,self.repo.version,
            self.repo.ops,self.repo.history,self.repo.authorized,self.repo.applied,self.audit.events))
        return self
    def commit(self):self.committed=True
    def __exit__(self,exc_type,_value,_tb):
        if exc_type is not None or not self.committed:
            (self.repo.snapshot,self.repo.state,self.repo.version,self.repo.ops,
             self.repo.history,self.repo.authorized,self.repo.applied,self.audit.events)=self.before
        return False

class PluginRuntimeRevalidationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.repo=_Repo();self.evidence=_Evidence(self.repo);self.audit=_Audit()
        self.owner=self._owner()
        self.command=RevalidatePluginInstallationCommand(self.repo.installation_id,
            self.repo.version,uuid.uuid4(),uuid.uuid4())
    def _owner(self):
        return PluginRuntimeRevalidationOwner(unit_of_work=lambda:_Uow(self.repo,self.audit),
            evidence=self.evidence,repository=self.repo,audit=self.audit,
            clock=lambda:datetime(2026,11,4,tzinfo=timezone.utc))
    def test_compatible_refresh_preserves_enabled_operations_and_appends_audit(self):
        result=self.owner.revalidate(self.command)
        self.assertEqual(result.installation_state,"ENABLED")
        self.assertEqual(result.compatibility_state,"COMPATIBLE")
        self.assertEqual(len(self.repo.ops),2);self.assertEqual(len(self.audit.events),1)
        self.assertTrue(self.repo.authorized)
    def test_incompatible_refresh_disables_each_operation_and_marks_installation(self):
        self.repo.compatible=False
        result=self.owner.revalidate(self.command)
        self.assertEqual(result.installation_state,"INCOMPATIBLE")
        self.assertEqual(result.disabled_operations,("document.export","document.render"))
        self.assertEqual(self.repo.ops,())
        self.assertEqual(self.repo.history,["document.export","document.render"])
        self.assertEqual(len(self.audit.events),3)
    def test_compatible_recovery_requires_explicit_reenable(self):
        self.repo=_Repo(state="INCOMPATIBLE");self.evidence=_Evidence(self.repo)
        self.owner=self._owner()
        cmd=RevalidatePluginInstallationCommand(self.repo.installation_id,self.repo.version,
                                                uuid.uuid4(),uuid.uuid4())
        result=self.owner.revalidate(cmd)
        self.assertEqual(result.installation_state,"DISABLED")
        self.assertEqual(self.repo.ops,())
    def test_stale_version_rejected_before_host_inspection(self):
        cmd=RevalidatePluginInstallationCommand(self.command.plugin_installation_id,
            self.command.expected_lock_version-1,self.command.actor_id,self.command.trace_id)
        with self.assertRaisesRegex(PluginRuntimeRevalidationOwnerError,"PLUGIN_LOCK_VERSION_CONFLICT"):
            self.owner.revalidate(cmd)
        self.assertEqual(self.evidence.calls,0)
    def test_package_digest_mismatch_fails_closed(self):
        self.evidence.bad_hash=True
        with self.assertRaisesRegex(PluginRuntimeRevalidationOwnerError,"PLUGIN_INSTALLATION_EVIDENCE_INVALID"):
            self.owner.revalidate(self.command)
        self.assertIsNone(self.repo.applied)
    def test_missing_installation_evidence_fails_closed(self):
        self.evidence.present=False
        with self.assertRaisesRegex(PluginRuntimeRevalidationOwnerError,"PLUGIN_INSTALLATION_EVIDENCE_INVALID"):
            self.owner.revalidate(self.command)
        self.assertIsNone(self.repo.applied)
    def test_audit_failure_rolls_back_state_and_operations(self):
        self.audit.fail=True
        with self.assertRaisesRegex(PluginRuntimeRevalidationOwnerError,"PLUGIN_REVALIDATION_STORE_UNAVAILABLE"):
            self.owner.revalidate(self.command)
        self.assertEqual(self.repo.state,"ENABLED");self.assertEqual(self.repo.version,4)
        self.assertEqual(len(self.repo.ops),2)
    def test_retired_installation_is_rejected(self):
        self.repo.state="RETIRED"
        with self.assertRaisesRegex(PluginRuntimeRevalidationOwnerError,"PLUGIN_REVALIDATION_NOT_ALLOWED"):
            self.owner.revalidate(self.command)

if __name__=="__main__":unittest.main()
