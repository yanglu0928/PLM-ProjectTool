from __future__ import annotations
import copy
import unittest
import uuid
from datetime import datetime, timezone
from plm_assistant.modules.plugin.application.activation_owner import (
    EnablePluginOperationsCommand, PluginActivationContext, PluginActivationOwner,
    PluginActivationOwnerError,
)

class _Repository:
    def __init__(self):
        self.target=uuid.uuid4(); self.old=uuid.uuid4()
        self.package=uuid.uuid4(); self.old_package=uuid.uuid4()
        self.states={self.target:"INSTALLED",self.old:"ENABLED"}
        self.versions={self.target:2,self.old:4}
        self.ops={self.target:frozenset(),self.old:frozenset({"document.render","document.export"})}
        self.history=[];self.authorized=False;self.applied=None
    def identify_plugin(self,_tx,*,installation_id):
        return "synthetic.echo" if installation_id==self.target else None
    def lock_plugin(self,_tx,*,plugin_id): self.locked=plugin_id
    def load_activation_context(self,_tx,*,installation_id):
        if installation_id!=self.target:return None
        return PluginActivationContext(
            "synthetic.echo",self.target,self.package,"VERIFIED",self.states[self.target],
            self.versions[self.target],{"schema_version":"1","os":"windows-11"},
            "COMPATIBLE",{"schema_version":"1","os":"windows-11"},
            frozenset({"document.render","document.export"}),dict(self.states),
            dict(self.versions),{self.target:self.package,self.old:self.old_package},
            dict(self.ops))
    def authorize_owner_writes(self,_tx):self.authorized=True
    def apply_activation(self,_tx,*,context,desired_operations,new_states,actor_id,changed_at):
        self.applied=(desired_operations,new_states)
        self.states.update(new_states)
        self.versions.update({key:self.versions[key]+1 for key in new_states})
        self.ops[self.target]=desired_operations
        self.ops[self.old]=frozenset(self.ops[self.old]-desired_operations)
    def append_operation_history(self,_tx,*,transition,actor_id,trace_id,audit_event_id):
        self.history.append(transition)

class _Audit:
    def __init__(self,fail=False):self.events=[];self.fail=fail
    def append(self,_tx,event):
        if self.fail:raise RuntimeError("synthetic audit failure")
        self.events.append(event);return uuid.uuid4()

class _Uow:
    def __init__(self,repo,audit):self.repo,self.audit=repo,audit;self.committed=False
    def __enter__(self):
        self.before=copy.deepcopy((self.repo.states,self.repo.versions,self.repo.ops,
                                   self.repo.history,self.audit.events));return self
    def commit(self):self.committed=True
    def __exit__(self,exc_type,_value,_tb):
        if exc_type is not None or not self.committed:
            (self.repo.states,self.repo.versions,self.repo.ops,
             self.repo.history,self.audit.events)=self.before
        return False

class PluginActivationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.repo=_Repository();self.audit=_Audit()
        self.owner=PluginActivationOwner(
            unit_of_work=lambda:_Uow(self.repo,self.audit),repository=self.repo,audit=self.audit,
            clock=lambda:datetime(2026,11,4,tzinfo=timezone.utc))
        self.cmd=EnablePluginOperationsCommand(
            self.repo.target,("document.render",),2,uuid.uuid4(),uuid.uuid4())
    def test_switches_operation_and_keeps_older_installation_and_other_operation(self):
        result=self.owner.enable(self.cmd)
        self.assertEqual(result.installation_state,"ENABLED")
        self.assertEqual(self.repo.states[self.repo.old],"ENABLED")
        self.assertEqual(self.repo.ops[self.repo.old],frozenset({"document.export"}))
        self.assertEqual(len(self.repo.history),2)
        self.assertEqual(len(self.audit.events),2)
        self.assertTrue(self.repo.authorized)
    def test_undeclared_operation_is_rejected_without_writes(self):
        cmd=EnablePluginOperationsCommand(self.cmd.plugin_installation_id,("admin.shell",),
            self.cmd.expected_lock_version,self.cmd.actor_id,self.cmd.trace_id)
        with self.assertRaisesRegex(PluginActivationOwnerError,"PLUGIN_OPERATION_NOT_DECLARED"):
            self.owner.enable(cmd)
        self.assertIsNone(self.repo.applied)
    def test_stale_target_lock_version_is_rejected(self):
        cmd=EnablePluginOperationsCommand(self.cmd.plugin_installation_id,self.cmd.operation_ids,
            1,self.cmd.actor_id,self.cmd.trace_id)
        with self.assertRaisesRegex(PluginActivationOwnerError,"PLUGIN_LOCK_VERSION_CONFLICT"):
            self.owner.enable(cmd)
    def test_exact_state_replay_is_noop(self):
        first=self.owner.enable(self.cmd)
        replay=EnablePluginOperationsCommand(self.cmd.plugin_installation_id,
            ("document.render",),first.lock_version,self.cmd.actor_id,self.cmd.trace_id)
        self.assertFalse(self.owner.enable(replay).changed)
        self.assertEqual(len(self.repo.history),2)
    def test_audit_failure_rolls_back_all_changes(self):
        self.audit.fail=True
        with self.assertRaisesRegex(PluginActivationOwnerError,"PLUGIN_ACTIVATION_STORE_UNAVAILABLE"):
            self.owner.enable(self.cmd)
        self.assertEqual(self.repo.states[self.repo.target],"INSTALLED")
        self.assertEqual(self.repo.ops[self.repo.old],
                         frozenset({"document.render","document.export"}))
        self.assertEqual(self.repo.history,[])

if __name__=="__main__":unittest.main()
