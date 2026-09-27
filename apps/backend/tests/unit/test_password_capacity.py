import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from plm_assistant.modules.auth.application.password_capacity import PasswordKdfCapacity


class CapacityTests(unittest.TestCase):
    def test_strict_bound_wait_and_unowned_release(self):
        for slots in (True,0,17,4.0,'4',None):
            with self.assertRaises(ValueError):PasswordKdfCapacity(slots=slots)
        gate=PasswordKdfCapacity()
        for timeout in (True,0,5.0,'5',None):
            with self.assertRaises(ValueError):gate.acquire(timeout=timeout)
        with self.assertRaises(ValueError):gate.release()
        self.assertEqual(gate.snapshot(),{'slots':4,'active':0,'peak':0})

    def test_nested_owned_acquisition_and_release(self):
        gate=PasswordKdfCapacity(slots=2)
        self.assertIs(gate.acquire(timeout=5),True);self.assertIs(gate.acquire(timeout=5),True)
        self.assertEqual(gate.snapshot(),{'slots':2,'active':2,'peak':2})
        gate.release();gate.release()
        self.assertEqual(gate.snapshot()['active'],0)
        with self.assertRaises(ValueError):gate.release()

    def test_foreign_thread_cannot_release_another_holder(self):
        gate=PasswordKdfCapacity(slots=1);gate.acquire(timeout=5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaises(ValueError):pool.submit(gate.release).result()
        self.assertEqual(gate.snapshot()['active'],1);gate.release()

    def test_actual_timeout_has_no_ownership_or_capacity_leak(self):
        gate=PasswordKdfCapacity(slots=1);gate.acquire(timeout=5)
        def waiter():
            self.assertIs(gate.acquire(timeout=5),False)
            with self.assertRaises(ValueError):gate.release()
        with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(waiter).result(timeout=7)
        self.assertEqual(gate.snapshot()['active'],1);gate.release()
        self.assertIs(gate.acquire(timeout=5),True);gate.release()

    def test_three_threads_share_total_two_and_recover_after_work_error(self):
        gate=PasswordKdfCapacity(slots=2);release=Event();two=Event()
        def work():
            gate.acquire(timeout=5)
            try:
                if gate.snapshot()['active']==2:two.set()
                self.assertTrue(release.wait(3))
                raise RuntimeError('Synthetic work failure')
            finally:gate.release()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(work) for _ in range(3)]
            try:self.assertTrue(two.wait(2));self.assertEqual(gate.snapshot()['active'],2)
            finally:release.set()
            for future in futures:
                with self.assertRaises(RuntimeError):future.result(timeout=4)
        self.assertEqual(gate.snapshot(),{'slots':2,'active':0,'peak':2})
