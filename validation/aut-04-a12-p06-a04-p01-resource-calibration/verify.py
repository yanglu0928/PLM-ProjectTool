"""Test-only slot calibration; production constants unchanged and failures stay failures."""
import argparse
import ctypes
from ctypes import wintypes
import json
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import BoundedSemaphore,Lock
from unittest.mock import patch
from plm_assistant.modules.auth.application import password_reset,password_change

spec=spec_from_file_location('_password_slot_benchmark',Path(__file__).resolve().parents[1]/'aut-04-a12-p06-a01-password-concurrency'/'verify.py')
bench=module_from_spec(spec);spec.loader.exec_module(bench)


class TrackedSlots:
    def __init__(self,size):
        self.gate=BoundedSemaphore(size);self.lock=Lock();self.active=0;self.peak=0;self.timeouts=0
    def acquire(self,*,timeout):
        acquired=self.gate.acquire(timeout=timeout)
        with self.lock:
            if acquired:self.active+=1;self.peak=max(self.peak,self.active)
            else:self.timeouts+=1
        return acquired
    def release(self):
        with self.lock:self.active-=1
        self.gate.release()
    def report(self):
        with self.lock:return {'active':self.active,'peak':self.peak,'timeouts':self.timeouts}


def peak_working_set():
    size=ctypes.c_size_t
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
            ('PeakWorkingSetSize',size),('WorkingSetSize',size),('QuotaPeakPagedPoolUsage',size),
            ('QuotaPagedPoolUsage',size),('QuotaPeakNonPagedPoolUsage',size),('QuotaNonPagedPoolUsage',size),
            ('PagefileUsage',size),('PeakPagefileUsage',size)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise RuntimeError('Local process memory observation unavailable')
    return counters.PeakWorkingSetSize


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--slots',type=int,choices=(4,8,16,20),required=True)
    parser.add_argument('--include-replay',action='store_true');args=parser.parse_args()
    reset=TrackedSlots(args.slots);change=TrackedSlots(args.slots)
    with patch.object(password_reset,'_RESET_HASH_SLOTS',reset),patch.object(password_change,'_CHANGE_KDF_SLOTS',change):
        bench.windows.http.m.fixture.main(exercise=lambda v:bench.windows.exercise(v,
            extra=lambda context,settings:bench.extra(context,settings,include_replay=args.include_replay)))
    assert reset.report()['active']==change.report()['active']==0
    print('PASSWORD_SLOT_CALIBRATION '+json.dumps({'experiment_only':True,'production_slots_unchanged':4,'test_slots':args.slots,
        'include_replay':args.include_replay,'reset_slots':reset.report(),'change_slots':change.report(),
        'process_peak_working_set_bytes':peak_working_set(),'acceptance_pass':bench.OUTCOME==[True]},sort_keys=True))
    if bench.OUTCOME!=[True]:raise SystemExit('PASSWORD_SLOT_CALIBRATION FAIL: original performance thresholds remain in effect')
