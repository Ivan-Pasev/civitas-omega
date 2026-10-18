import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import importlib.util
spec=importlib.util.spec_from_file_location('source_readiness',Path(__file__).resolve().parents[1]/'scripts'/'source_readiness.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ori=mod.VALID_SCOPES['public']
        self.addCleanup(lambda:mod.VALID_SCOPES.__setitem__('public',self.ori))
        mod.VALID_SCOPES['public']=(self.ori[0],self.ori[1],2,4)
        self.files={'SOURCE_SHA256.json':hashlib.sha256(b'{}').hexdigest(),'a.txt':hashlib.sha256(b'alpha').hexdigest()}
        self.registry={'schema':mod.SCHEMA,'scope':'public','repository':self.ori[0],'candidate_archive_sha256':self.ori[1],'expected_file_count':2,'expected_tests':4,'files':self.files}
    def test_full_success_is_only_readiness(self):
        (self.root/'SOURCE_SHA256.json').write_bytes(b'{}')
        (self.root/'a.txt').write_bytes(b'alpha')
        r=mod.evaluate(self.root,self.registry)
        self.assertEqual(r['source_readiness'],'READY_FOR_FULL_OFFLINE_SUITE')
        self.assertEqual(r['matched_files'],2)
        self.assertFalse(r['full_suite_executed'])
        self.assertFalse(r['remote_head_authenticated'])
    def test_missing_reports_hold_not_pass(self):
        r=mod.evaluate(self.root,self.registry)
        self.assertEqual(set(r['missing_paths']),set(self.files))
        self.assertEqual(r['source_readiness'],'HOLD_INCOMPLETE_OR_DIFFERENT_SOURCE')
    def test_altered_not_smoothed(self):
        (self.root/'SOURCE_SHA256.json').write_bytes(b'{}')
        (self.root/'a.txt').write_bytes(b'bad')
        r=mod.evaluate(self.root,self.registry)
        self.assertEqual(r['altered_paths'],['a.txt'])
        self.assertEqual(r['matched_files'],1)
    def test_wrong_repo_invalid(self):
        self.registry['repository']='Ivan-Pasev/civitas-omega-lab'
        with self.assertRaisesRegex(mod.GateInputError,'identity'):
            mod.evaluate(self.root,self.registry)
    def test_wrong_digest_invalid(self):
        self.registry['candidate_archive_sha256']='0'*64
        with self.assertRaisesRegex(mod.GateInputError,'identity'):
            mod.evaluate(self.root,self.registry)
    def test_wrong_count_invalid(self):
        self.registry['expected_file_count']=3
        with self.assertRaisesRegex(mod.GateInputError,'identity'):
            mod.evaluate(self.root,self.registry)
    def test_relative_traversal_invalid(self):
        self.files['../evil']=self.files.pop('a.txt')
        with self.assertRaisesRegex(mod.GateInputError,'unsafe'):
            mod.evaluate(self.root,self.registry)
    def test_backslash_invalid(self):
        self.files['..\\evil']=self.files.pop('a.txt')
        with self.assertRaisesRegex(mod.GateInputError,'path'):
            mod.evaluate(self.root,self.registry)
    def test_bad_hash_invalid(self):
        self.files['a.txt']='invalid'
        with self.assertRaisesRegex(mod.GateInputError,'digest'):
            mod.evaluate(self.root,self.registry)
    def test_symlink_rejected(self):
        (self.root/'SOURCE_SHA256.json').write_bytes(b'{}')
        (self.root/'a.txt').symlink_to('/etc/passwd')
        self.assertEqual(mod.evaluate(self.root,self.registry)['unsafe_paths'],['a.txt'])
    def test_abs_path_rejected(self):
        self.files['/tmp/x']=self.files.pop('a.txt')
        with self.assertRaisesRegex(mod.GateInputError,'path'):
            mod.evaluate(self.root,self.registry)
    def test_registry_no_manifest(self):
        self.files.pop('SOURCE_SHA256.json')
        self.files['b.txt']='a'*64
        with self.assertRaisesRegex(mod.GateInputError,'self-contained'):
            mod.evaluate(self.root,self.registry)
if __name__=='__main__':unittest.main()
