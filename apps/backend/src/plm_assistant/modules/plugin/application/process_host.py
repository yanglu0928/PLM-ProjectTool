"""Bounded JSON-RPC stdio transport for one already-authorized Plugin call."""
from __future__ import annotations
import ctypes, json, math, os, shutil, signal, subprocess, tempfile, threading, time, uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
SAFE_ENV=frozenset({"COMSPEC","LANG","PATH","PATHEXT","SYSTEMDRIVE","SYSTEMROOT","WINDIR"})
SECRET_FIELDS=frozenset({"api_key","apikey","database_url","connection_string","credential","credentials","private_key","license_private_key","secret"})
CHUNK=4096
MAX_TIMEOUT=300.0

class PluginProcessHostError(RuntimeError):
    """Sanitized failure without request data or child text."""
    def __init__(self, code: str, *, stage: str | None = None, native_code: int | None = None):
        self.code=code
        self.stage=stage
        self.native_code=native_code if type(native_code) is int else None
        super().__init__(code)

@dataclass(frozen=True,slots=True)
class PluginProcessResult:
    request_id: str
    result: Any

def _pairs(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError("duplicate JSON member")
        result[key]=value
    return result

def _constant(_):
    raise ValueError("nonfinite JSON")

def _secret(value,depth=0):
    if depth>32: raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
    if isinstance(value,dict):
        return any((type(k) is str and k.casefold().replace("-","_") in SECRET_FIELDS)
                   or _secret(v,depth+1) for k,v in value.items())
    if isinstance(value,(list,tuple)): return any(_secret(v,depth+1) for v in value)
    return False

def _validate(executable,package_root,entry_point,work_root):
    if (not isinstance(executable,Path) or not executable.is_absolute() or executable.is_symlink() or not executable.is_file()
        or not isinstance(package_root,Path) or not package_root.is_absolute() or package_root.is_symlink() or not package_root.is_dir()
        or not isinstance(work_root,Path) or not work_root.is_absolute() or work_root.is_symlink() or not work_root.is_dir()
        or type(entry_point) is not str or not entry_point or "\\" in entry_point or ":" in entry_point):
        raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
    rel=PurePosixPath(entry_point)
    if rel.is_absolute() or rel.as_posix()!=entry_point or any(x in {"",".",".."} for x in entry_point.split("/")):
        raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
    root=package_root.resolve(strict=True); candidate=root.joinpath(*rel.parts); cursor=candidate
    while cursor!=root:
        if cursor.is_symlink(): raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
        cursor=cursor.parent
    entry=candidate.resolve(strict=True)
    if root not in entry.parents or not entry.is_file(): raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
    return executable.resolve(strict=True),entry,work_root.resolve(strict=True)

class _Tree:
    def __init__(self,proc):
        self.proc=proc; self.job=None; self.stage=None
        if os.name=="nt": self._win(proc)
        elif os.name=="posix": self.group=proc.pid
        else: self.group=None
    def _win(self,proc):
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_=[("a",ctypes.c_longlong),("b",ctypes.c_longlong),("flags",wintypes.DWORD),
                      ("min",ctypes.c_size_t),("max",ctypes.c_size_t),("active",wintypes.DWORD),
                      ("affinity",ctypes.c_size_t),("priority",wintypes.DWORD),("schedule",wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(n,ctypes.c_ulonglong) for n in ("r1","r2","r3","r4","r5","r6")]
        class Extended(ctypes.Structure):
            _fields_=[("basic",Basic),("io",IO),("proc",ctypes.c_size_t),("job",ctypes.c_size_t),
                      ("proc_peak",ctypes.c_size_t),("job_peak",ctypes.c_size_t)]
        k=ctypes.WinDLL("kernel32",use_last_error=True)
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]; k.CreateJobObjectW.restype=wintypes.HANDLE
        k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]; k.SetInformationJobObject.restype=wintypes.BOOL
        k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; k.OpenProcess.restype=wintypes.HANDLE
        k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]; k.AssignProcessToJobObject.restype=wintypes.BOOL
        k.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT]; k.TerminateJobObject.restype=wintypes.BOOL
        k.CloseHandle.argtypes=[wintypes.HANDLE]; k.CloseHandle.restype=wintypes.BOOL
        self.stage="job_create"; job=k.CreateJobObjectW(None,None)
        if not job: raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
        self.k,self.job=k,job
        try:
            self.stage="job_configure"
            limits=Extended(); limits.basic.flags=0x2000
            if not k.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
                raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
            self.stage="process_open"; ph=k.OpenProcess(0x0100|0x0001,False,proc.pid)
            if not ph: raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
            self.stage="job_assign"; attached=bool(k.AssignProcessToJobObject(job,ph))
            native=ctypes.get_last_error() if not attached else None
            k.CloseHandle(ph)
            if not attached: raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=native)
            self._resume_primary_thread(proc.pid)
            self.stage="running"
        except PluginProcessHostError:
            self._close_windows_job(); raise
        except Exception:
            stage=self.stage; native=ctypes.get_last_error()
            self._close_windows_job()
            raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=stage,native_code=native) from None
    def _resume_primary_thread(self,pid):
        from ctypes import wintypes
        class ThreadEntry(ctypes.Structure):
            _fields_=[("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),
                      ("th32ThreadID",wintypes.DWORD),("th32OwnerProcessID",wintypes.DWORD),
                      ("tpBasePri",wintypes.LONG),("tpDeltaPri",wintypes.LONG),("dwFlags",wintypes.DWORD)]
        k=self.k
        k.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
        k.Thread32First.argtypes=[wintypes.HANDLE,ctypes.POINTER(ThreadEntry)]; k.Thread32First.restype=wintypes.BOOL
        k.Thread32Next.argtypes=[wintypes.HANDLE,ctypes.POINTER(ThreadEntry)]; k.Thread32Next.restype=wintypes.BOOL
        k.OpenThread.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; k.OpenThread.restype=wintypes.HANDLE
        k.ResumeThread.argtypes=[wintypes.HANDLE]; k.ResumeThread.restype=wintypes.DWORD
        self.stage="thread_snapshot"; snapshot=k.CreateToolhelp32Snapshot(0x00000004,0)
        if not snapshot or snapshot==ctypes.c_void_p(-1).value:
            raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
        thread=None
        try:
            self.stage="thread_enumerate"
            entry=ThreadEntry(); entry.dwSize=ctypes.sizeof(ThreadEntry)
            found=k.Thread32First(snapshot,ctypes.byref(entry)); thread_id=None
            while found:
                if entry.th32OwnerProcessID==pid:
                    thread_id=entry.th32ThreadID; break
                found=k.Thread32Next(snapshot,ctypes.byref(entry))
            if thread_id is None:
                raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
            self.stage="thread_open"; thread=k.OpenThread(0x0002,False,thread_id)
            if not thread:
                raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=ctypes.get_last_error())
            self.stage="thread_resume"; previous=k.ResumeThread(thread)
            if previous!=1:
                raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED",stage=self.stage,native_code=int(previous))
        finally:
            if thread: k.CloseHandle(thread)
            k.CloseHandle(snapshot)
    def _close_windows_job(self):
        if self.job:
            try: self.k.TerminateJobObject(self.job,1)
            finally:
                self.k.CloseHandle(self.job); self.job=None
    def terminate(self):
        if self.job: self.k.TerminateJobObject(self.job,1)
        elif os.name=="posix":
            try: os.killpg(self.group,signal.SIGKILL)
            except (ProcessLookupError,PermissionError):
                if self.proc.poll() is None: self.proc.kill()
        elif self.proc.poll() is None: self.proc.kill()
    def close(self):
        if self.job:
            self.k.CloseHandle(self.job); self.job=None
        elif os.name=="posix":
            try: os.killpg(self.group,signal.SIGKILL)
            except (ProcessLookupError,PermissionError): pass

class PluginProcessHost:
    """Transport only; trust/install/capability checks stay with the caller."""
    def __init__(self,*,max_request_bytes=1_048_576,max_response_bytes=1_048_576,max_stderr_bytes=16_384):
        if any(type(x) is not int or x<1 for x in (max_request_bytes,max_response_bytes,max_stderr_bytes)):
            raise ValueError("positive limits required")
        self.req=max_request_bytes; self.out=max_response_bytes; self.err=max_stderr_bytes
    def invoke(self,*,executable:Path,package_root:Path,entry_point:str,work_root:Path,
               plugin_id:str,api_version:str,method:str,params:Mapping[str,object],timeout_seconds:float=30.0):
        executable,entry,work_root=_validate(executable,package_root,entry_point,work_root)
        if (type(plugin_id) is not str or not plugin_id or len(plugin_id)>128
            or type(api_version) is not str or not api_version or len(api_version)>64
            or type(method) is not str or not method or len(method.encode("utf-8"))>256
            or type(params) is not dict or _secret(params)
            or type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds)
            or not 0<timeout_seconds<=MAX_TIMEOUT):
            raise PluginProcessHostError("PLUGIN_INVALID_REQUEST")
        request_id=uuid.uuid4().hex
        try:
            payload=(json.dumps({"jsonrpc":"2.0","id":request_id,"method":method,"params":params},
                ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
        except (TypeError,ValueError,UnicodeError): raise PluginProcessHostError("PLUGIN_INVALID_REQUEST") from None
        if len(payload)>self.req: raise PluginProcessHostError("PLUGIN_REQUEST_TOO_LARGE")
        work=Path(tempfile.mkdtemp(prefix="plm-plugin-invoke-",dir=work_root))
        proc=tree=None; stdout=bytearray(); stderr=bytearray(); overflow=threading.Event(); read_error=threading.Event()
        def drain(stream,buffer,limit):
            try:
                while True:
                    data=stream.read(CHUNK)
                    if not data: return
                    if len(buffer)+len(data)<=limit: buffer.extend(data)
                    else: overflow.set()
            except Exception: read_error.set()
        def send(stream):
            try: stream.write(payload); stream.flush()
            except (BrokenPipeError,OSError): pass
            finally:
                try: stream.close()
                except OSError: pass
        try:
            flags=0; kwargs={}
            if os.name=="nt": flags=getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"CREATE_SUSPENDED",0)
            elif os.name=="posix": kwargs["start_new_session"]=True
            env={k:v for k,v in os.environ.items() if k.upper() in SAFE_ENV and type(v) is str}
            env.update({"TEMP":str(work),"TMP":str(work),"PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1",
                "PYTHONDONTWRITEBYTECODE":"1","PLM_PLUGIN_WORK_DIR":str(work),
                "PLM_PLUGIN_ID":plugin_id,"PLM_PLUGIN_API_VERSION":api_version})
            proc=subprocess.Popen([str(executable),"-B",str(entry)],cwd=work,env=env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                shell=False,close_fds=True,creationflags=flags,**kwargs)
            tree=_Tree(proc)
            assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
            readers=[threading.Thread(target=drain,args=(proc.stdout,stdout,self.out),daemon=True),
                     threading.Thread(target=drain,args=(proc.stderr,stderr,self.err),daemon=True)]
            writer=threading.Thread(target=send,args=(proc.stdin,),daemon=True)
            for t in readers+[writer]: t.start()
            deadline=time.monotonic()+timeout_seconds; failure=None
            while proc.poll() is None:
                if overflow.wait(0.01): failure="PLUGIN_OUTPUT_TOO_LARGE"; tree.terminate(); break
                if time.monotonic()>=deadline: failure="PLUGIN_TIMEOUT"; tree.terminate(); break
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tree.terminate(); proc.kill(); proc.wait(timeout=5); failure=failure or "PLUGIN_PROCESS_CLEANUP_FAILED"
            for t in readers+[writer]: t.join(timeout=2)
            if any(t.is_alive() for t in readers+[writer]):
                tree.terminate(); failure=failure or "PLUGIN_PROCESS_CLEANUP_FAILED"
            if read_error.is_set(): failure=failure or "PLUGIN_INVALID_RESPONSE"
            if failure: raise PluginProcessHostError(failure)
            if overflow.is_set(): raise PluginProcessHostError("PLUGIN_OUTPUT_TOO_LARGE")
            if proc.returncode!=0: raise PluginProcessHostError("PLUGIN_CRASH")
            try:
                lines=[line for line in stdout.decode("utf-8","strict").splitlines() if line.strip()]
                if len(lines)!=1: raise ValueError("line count")
                response=json.loads(lines[0],object_pairs_hook=_pairs,parse_constant=_constant)
            except Exception: raise PluginProcessHostError("PLUGIN_INVALID_RESPONSE") from None
            if type(response) is not dict or response.get("jsonrpc")!="2.0" or response.get("id")!=request_id:
                raise PluginProcessHostError("PLUGIN_INVALID_RESPONSE")
            if set(response)=={"jsonrpc","id","error"}: raise PluginProcessHostError("PLUGIN_REMOTE_ERROR")
            if set(response)!={"jsonrpc","id","result"}: raise PluginProcessHostError("PLUGIN_INVALID_RESPONSE")
            return PluginProcessResult(request_id,response["result"])
        except PluginProcessHostError: raise
        except Exception: raise PluginProcessHostError("PLUGIN_PROCESS_START_FAILED") from None
        finally:
            if tree is not None: tree.close()
            if proc is not None:
                for stream in (proc.stdin,proc.stdout,proc.stderr):
                    if stream is not None:
                        try: stream.close()
                        except OSError: pass
                if proc.poll() is None:
                    try: proc.kill(); proc.wait(timeout=5)
                    except Exception: pass
            try:
                wr=work_root.resolve(strict=True); wd=work.resolve(strict=True)
                if wd.parent==wr and wd.name.startswith("plm-plugin-invoke-") and not work.is_symlink():
                    shutil.rmtree(wd)
            except (OSError,RuntimeError): pass
