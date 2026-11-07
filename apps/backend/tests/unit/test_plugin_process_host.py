from __future__ import annotations
import os,sys,tempfile,unittest
from pathlib import Path
from plm_assistant.modules.plugin.application.process_host import PluginProcessHost,PluginProcessHostError

class PluginProcessHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner=os.environ.get("RUNNER_TEMP")
        if not runner: raise unittest.SkipTest("Hosted RUNNER_TEMP required")
        root=Path(runner).resolve(strict=True)
        if os.name=="nt" and root.drive.upper()=="C:": raise unittest.SkipTest("C drive is prohibited")
        cls.temp=tempfile.TemporaryDirectory(prefix="plm-plugin-host-test-",dir=root)
        cls.root=Path(cls.temp.name).resolve(strict=True); cls.package=cls.root/"plugin"; cls.package.mkdir()
        cls.work=cls.root/"work"; cls.work.mkdir()
        cls.host=PluginProcessHost(max_request_bytes=4096,max_response_bytes=4096,max_stderr_bytes=512)
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,"temp"): cls.temp.cleanup()
    def script(self,text):
        (self.package/"entry.py").write_text(text,encoding="utf-8"); return "entry.py"
    def invoke(self,entry,*,timeout=2.0,params=None):
        return self.host.invoke(executable=Path(sys.executable).resolve(strict=True),package_root=self.package,
            entry_point=entry,work_root=self.work,plugin_id="synthetic.plugin-host-probe",
            api_version="1",method="probe",params=params or {},timeout_seconds=timeout)
    def test_round_trip_and_workdir_cleanup(self):
        entry=self.script("""
import json, os, sys
r=json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc":"2.0","id":r["id"],"result":{"method":r["method"],"cwd":os.getcwd()}}))
""")
        got=self.invoke(entry)
        self.assertEqual("probe",got.result["method"])
        self.assertTrue(Path(got.result["cwd"]).name.startswith("plm-plugin-invoke-"))
        self.assertEqual([],list(self.work.iterdir()))
    def test_secret_environment_is_filtered(self):
        entry=self.script("""
import json, os, sys
r=json.loads(sys.stdin.readline())
names=("DATABASE_URL","DEEPSEEK_API_KEY","OPENAI_API_KEY","KEY")
print(json.dumps({"jsonrpc":"2.0","id":r["id"],"result":{k:k in os.environ for k in names}}))
""")
        names=("DATABASE_URL","DEEPSEEK_API_KEY","OPENAI_API_KEY","KEY"); old={k:os.environ.get(k) for k in names}
        try:
            for k in names: os.environ[k]="synthetic-secret-sentinel"
            got=self.invoke(entry)
        finally:
            for k,v in old.items():
                if v is None: os.environ.pop(k,None)
                else: os.environ[k]=v
        self.assertEqual({k:False for k in names},got.result)
    def test_secret_params_rejected_before_spawn(self):
        with self.assertRaises(PluginProcessHostError) as e:
            self.invoke(self.script("raise SystemExit(0)\n"),params={"nested":{"database_url":"synthetic-secret"}})
        self.assertEqual("PLUGIN_INVALID_REQUEST",e.exception.code)
    def test_bad_json_and_wrong_id_fail_closed(self):
        with self.assertRaises(PluginProcessHostError) as e: self.invoke(self.script("print('bad')\n"))
        self.assertEqual("PLUGIN_INVALID_RESPONSE",e.exception.code)
        entry=self.script("""
import json,sys
r=json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc":"2.0","id":"wrong","result":0}))
""")
        with self.assertRaises(PluginProcessHostError) as e: self.invoke(entry)
        self.assertEqual("PLUGIN_INVALID_RESPONSE",e.exception.code)
    def test_duplicate_json_and_remote_error_sanitized(self):
        duplicate=self.script("""
import json,sys
r=json.loads(sys.stdin.readline())
sys.stdout.write('{"jsonrpc":"2.0","id":"' + r["id"] + '","id":"other","result":0}\\n')
""")
        with self.assertRaises(PluginProcessHostError) as e: self.invoke(duplicate)
        self.assertEqual("PLUGIN_INVALID_RESPONSE",e.exception.code)
        remote=self.script("""
import json,sys
r=json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc":"2.0","id":r["id"],"error":{"code":1,"message":"SENSITIVE"}}))
""")
        with self.assertRaises(PluginProcessHostError) as e: self.invoke(remote)
        self.assertEqual("PLUGIN_REMOTE_ERROR",e.exception.code); self.assertNotIn("SENSITIVE",str(e.exception))
    def test_timeout_and_output_limit(self):
        with self.assertRaises(PluginProcessHostError) as e:
            self.invoke(self.script("import time\ntime.sleep(5)\n"),timeout=.15)
        self.assertEqual("PLUGIN_TIMEOUT",e.exception.code)
        host=PluginProcessHost(max_request_bytes=4096,max_response_bytes=128,max_stderr_bytes=128)
        entry=self.script("print('x'*10000)\n")
        with self.assertRaises(PluginProcessHostError) as e:
            host.invoke(executable=Path(sys.executable).resolve(strict=True),package_root=self.package,
                entry_point=entry,work_root=self.work,plugin_id="synthetic.plugin-host-probe",
                api_version="1",method="probe",params={},timeout_seconds=2)
        self.assertEqual("PLUGIN_OUTPUT_TOO_LARGE",e.exception.code)
    def test_crash_and_request_size_fail_closed(self):
        with self.assertRaises(PluginProcessHostError) as e:
            self.invoke(self.script("import sys\nsys.stderr.write('SECRET-DIAG')\nsys.exit(9)\n"))
        self.assertEqual("PLUGIN_CRASH",e.exception.code); self.assertNotIn("SECRET-DIAG",str(e.exception))
        entry=self.script("""
import json,sys
r=json.loads(sys.stdin.readline())
print(json.dumps({"jsonrpc":"2.0","id":r["id"],"result":0}))
""")
        with self.assertRaises(PluginProcessHostError) as e: self.invoke(entry,params={"large":"x"*5000})
        self.assertEqual("PLUGIN_REQUEST_TOO_LARGE",e.exception.code)
if __name__=="__main__": unittest.main()
