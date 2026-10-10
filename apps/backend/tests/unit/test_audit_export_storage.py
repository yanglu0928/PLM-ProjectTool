"""Real temporary files: storage primitives, NOT authorization or publication."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4, UUID
from plm_assistant.modules.document.application.audit_export_storage import (
    AuditFileCoordinate, AuditFileContent, AuditFileStorageError,
)
from plm_assistant.modules.document.infrastructure.audit_export_storage import (
    LocalAuditExportFileStorage, _locators, _BoundedSink,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError


class AuditExportStorageTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="plm-audit-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.local=LocalFileStorage(self.root)
        self.storage=LocalAuditExportFileStorage(self.local)

    def coordinate(self,scope="DEPLOYMENT"):
        return AuditFileCoordinate(uuid4(),scope,uuid4() if scope=="PROJECT" else None)

    def write(self,coordinate,data):
        with self.storage.staging_sink(coordinate) as sink:
            self.assertEqual(sink.write(data),len(data))
        expected=AuditFileContent(coordinate,hashlib.sha256(data).digest(),len(data))
        self.assertEqual(self.storage.verify_staged(expected),expected)
        return expected

    def test_actual_two_scopes_and_empty_files(self):
        for scope in ("DEPLOYMENT","PROJECT"):
            for data in (b"",'{"action":"中文"}\n'.encode()):
                coordinate=self.coordinate(scope); expected=self.write(coordinate,data)
                self.assertEqual(self.storage.inspect(expected),"STAGE_ONLY")
                self.assertEqual(self.storage.promote(expected),expected)
                self.assertEqual(self.storage.inspect(expected),"FINAL_VERIFIED")
                stage,final=_locators(coordinate)
                self.assertFalse((self.root/stage).exists())
                self.assertEqual((self.root/final).read_bytes(),data)
                self.assertFalse(hasattr(expected,"locator"))

    def test_same_id_is_never_overwritten(self):
        coordinate=self.coordinate(); expected=self.write(coordinate,b"original")
        with self.assertRaises(AuditFileStorageError):
            with self.storage.staging_sink(coordinate): pass
        self.storage.promote(expected)
        with self.assertRaises(AuditFileStorageError):
            with self.storage.staging_sink(coordinate): pass
        _,final=_locators(coordinate)
        self.assertEqual((self.root/final).read_bytes(),b"original")
        next_generation=replace(coordinate,file_id=uuid4())
        self.storage.promote(self.write(next_generation,b"next generation"))
        self.assertEqual((self.root/final).read_bytes(),b"original")

    def test_bad_hash_and_size_do_not_promote(self):
        coordinate=self.coordinate(); expected=self.write(coordinate,b"full")
        for wrong in (replace(expected,sha256=b"x"*32),replace(expected,size_bytes=3)):
            with self.assertRaises(AuditFileStorageError): self.storage.verify_staged(wrong)
            with self.assertRaises(AuditFileStorageError): self.storage.promote(wrong)
        stage,final=_locators(coordinate)
        self.assertTrue((self.root/stage).exists());self.assertFalse((self.root/final).exists())

    def test_exception_keeps_only_private_partial_file(self):
        coordinate=self.coordinate()
        with self.assertRaisesRegex(RuntimeError,"synthetic renderer failed"):
            with self.storage.staging_sink(coordinate) as sink:
                sink.write(b"partial");raise RuntimeError("synthetic renderer failed")
        stage,final=_locators(coordinate)
        self.assertEqual((self.root/stage).read_bytes(),b"partial")
        self.assertFalse((self.root/final).exists())

    def test_bound_rejects_without_writing_extra_bytes(self):
        coordinate=self.coordinate()
        with patch("plm_assistant.modules.document.infrastructure.audit_export_storage.MAX_AUDIT_FILE_BYTES",4):
            with self.assertRaises(AuditFileStorageError) as caught:
                with self.storage.staging_sink(coordinate) as sink:
                    sink.write(b"1234");sink.write(b"5")
        self.assertEqual(caught.exception.code,"FILE_SIZE_EXCEEDED")
        stage,_=_locators(coordinate);self.assertEqual((self.root/stage).read_bytes(),b"1234")

    def test_short_write_and_simulated_disk_full(self):
        class Stream:
            def __init__(self,value):self.value=value
            def write(self,data):
                if isinstance(self.value,Exception):raise self.value
                return self.value
        for result in (None,True,0,2,OSError(28,"synthetic disk full")):
            with self.assertRaises(AuditFileStorageError) as caught: _BoundedSink(Stream(result)).write(b"abc")
            self.assertEqual(str(caught.exception),"FILE_UNAVAILABLE")
        with self.assertRaises(AuditFileStorageError): _BoundedSink(Stream(3)).write(bytearray(b"abc"))

    def test_fsync_failure_is_not_success(self):
        coordinate=self.coordinate()
        with patch("plm_assistant.modules.document.infrastructure.audit_export_storage.os.fsync",side_effect=OSError(28,"synthetic disk full")):
            with self.assertRaises(AuditFileStorageError):
                with self.storage.staging_sink(coordinate) as sink:sink.write(b"full")
        stage,final=_locators(coordinate)
        self.assertEqual((self.root/stage).read_bytes(),b"full")
        self.assertFalse((self.root/final).exists())

    def test_caught_sink_error_still_prevents_successful_close(self):
        coordinate=self.coordinate()
        with self.assertRaises(AuditFileStorageError):
            with self.storage.staging_sink(coordinate) as sink:
                try:sink.write("not bytes")
                except AuditFileStorageError:pass

    def test_actual_renderer_writes_verified_private_file(self):
        from datetime import datetime,timedelta,timezone
        from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
        from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
        from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
        from plm_assistant.modules.audit.application.render_export import AuditExportRenderer
        from plm_assistant.modules.audit.domain.capture_membership import digest_members
        now=datetime.now(timezone.utc)
        spec=AuditExportSpec("DEPLOYMENT",None,"SECURITY_REVIEW",now-timedelta(hours=1),now+timedelta(hours=1))
        intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        membership=digest_members(())
        capture=CapturedAuditExport(intent.export_id,intent.actor_id,"DEPLOYMENT",None,now,now,0,membership.sha256,
            membership.version,intent.intent_hash,intent.policy_version,intent.projection_version,intent.format_version)
        coordinate=self.coordinate()
        with self.storage.staging_sink(coordinate) as sink:
            result=AuditExportRenderer().render(intent=intent,capture=capture,items=(),sink=sink)
        proof=AuditFileContent(coordinate,bytes.fromhex(result.file_sha256),result.byte_count)
        self.assertEqual(self.storage.verify_staged(proof),proof)
        self.assertEqual(result.member_count,0)
        self.assertEqual(self.storage.promote(proof),proof)

    def test_final_only_recovery_revalidates_content(self):
        coordinate=self.coordinate();expected=self.write(coordinate,b"full")
        self.storage.promote(expected)
        self.assertEqual(self.storage.promote(expected,mode="final_only"),expected)
        _,final=_locators(coordinate);(self.root/final).write_bytes(b"bad!")
        self.assertEqual(self.storage.inspect(expected),"FINAL_INVALID")
        with self.assertRaises(AuditFileStorageError):self.storage.promote(expected,mode="final_only")

    def test_actual_linked_pair_crash_window(self):
        coordinate=self.coordinate();expected=self.write(coordinate,b"linked")
        original=os.unlink
        def fail_stage(path,*args,**kwargs):
            if Path(path)==self.root/_locators(coordinate)[0]:raise OSError("synthetic crash after hard link")
            return original(path,*args,**kwargs)
        with patch("plm_assistant.modules.document.infrastructure.local_storage.os.unlink",side_effect=fail_stage):
            with self.assertRaises(AuditFileStorageError):self.storage.promote(expected)
        self.assertEqual(self.storage.inspect(expected),"LINKED_PAIR")
        self.assertEqual(self.storage.promote(expected,mode="linked_pair"),expected)
        self.assertEqual(self.storage.inspect(expected),"FINAL_VERIFIED")

    def test_unrelated_pair_is_never_recovered(self):
        coordinate=self.coordinate();expected=self.write(coordinate,b"same")
        stage,final=_locators(coordinate)
        (self.root/final).parent.mkdir(parents=True)
        (self.root/final).write_bytes(b"same")
        self.assertEqual(self.storage.inspect(expected),"BOTH_UNRELATED")
        with self.assertRaises(AuditFileStorageError):self.storage.promote(expected,mode="linked_pair")
        with self.assertRaises(AuditFileStorageError):self.storage.promote(expected,mode="final_only")
        self.assertTrue((self.root/stage).exists());self.assertTrue((self.root/final).exists())

    def test_audit_namespace_is_not_upload_cleanup_inventory(self):
        self.write(self.coordinate(),b"private")
        self.write(self.coordinate("PROJECT"),b"private")
        self.assertEqual(self.local.scan_staging_candidates().candidates,())
        upload=uuid4();stage,_=self.local.locators(scope="GLOBAL",project_id=None,file_object_id=upload)
        with self.local.reserve_staging(stage) as stream:stream.write(b"ordinary")
        self.assertEqual(tuple(item.upload_id for item in self.local.scan_staging_candidates().candidates),(upload,))

    def test_coordinates_and_physical_paths_fail_closed(self):
        for values in (("../escape","DEPLOYMENT",None),(UUID(int=0),"DEPLOYMENT",None),
            (uuid4(),"GLOBAL",None),(uuid4(),"DEPLOYMENT",uuid4()),(uuid4(),"PROJECT",None)):
            with self.assertRaises(AuditFileStorageError):AuditFileCoordinate(*values)
        coordinate=self.coordinate();stage,_=_locators(coordinate)
        for wrong in (stage.upper(),stage.replace("generated","../generated"),"C:/"+stage,stage.replace("deployment","global")):
            with self.assertRaises(LocalStorageError):self.local.reserve_staging(wrong)
        with self.assertRaises(AuditFileStorageError):AuditFileContent(coordinate,b"short",0)
        with self.assertRaises(AuditFileStorageError):AuditFileContent(coordinate,b"h"*32,True)
