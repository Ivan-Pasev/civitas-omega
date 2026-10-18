import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
SCRIPT=Path(__file__).resolve().parents[1]/'verify_r3_commit.py'
spec=importlib.util.spec_from_file_location('verify_r3_commit',SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def call(cwd,*args):
    p=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,check=True)
    return p.stdout.decode().strip()
class CommitParity(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.d=Path(self.t.name)
        self.repo=self.d/'civitas-omega';self.repo.mkdir()
        call(self.repo,'init','-b','main')
        call(self.repo,'config','user.name','GH04 Fixture')
        call(self.repo,'config','user.email','fixture@example.invalid')
        call(self.repo,'remote','add','origin','https://github.com/Ivan-Pasev/civitas-omega.git')
        self.file=self.repo/'demo.txt';self.file.write_bytes(b'a\n')
        self.cfg=mod.EXPECTED['public'].copy()
        self.addCleanup(lambda:mod.EXPECTED.__setitem__('public',self.cfg))
        self.archive=self.d/'local.zip'
        self.freeze({'demo.txt':b'a\n'})
        call(self.repo,'add','.')
        call(self.repo,'commit','-m','fixture')
        self.head=call(self.repo,'rev-parse','HEAD')
    def freeze(self,contents):
        b=io.BytesIO();root='civitas-omega/'
        with zipfile.ZipFile(b,'w') as z:
            for name,payload in contents.items():z.writestr(root+name,payload)
            z.writestr(root+'SOURCE_SHA256.json',json.dumps({'files':{p:hashlib.sha256(v).hexdigest() for p,v in contents.items()}}))
        self.archive.write_bytes(b.getvalue())
        mod.EXPECTED['public']={**self.cfg,'archive':self.archive.name,'sha256':hashlib.sha256(b.getvalue()).hexdigest(),'files':len(contents)+1}
    def test_missing_manifest_from_commit_fails(self):
        result=mod.verify(self.repo,self.archive,'public',self.head)
        self.assertEqual(result['source_parity'],'FAIL')
        self.assertIn('SOURCE_SHA256.json',[x['path'] for x in result['mismatches']])
    def test_exact_commit_has_verified_parity(self):
        with zipfile.ZipFile(self.archive) as z:
            (self.repo/'SOURCE_SHA256.json').write_bytes(z.read('civitas-omega/SOURCE_SHA256.json'))
        call(self.repo,'add','.');call(self.repo,'commit','-m','manifest')
        sha=call(self.repo,'rev-parse','HEAD')
        result=mod.verify(self.repo,self.archive,'public',sha)
        self.assertEqual(result['source_parity'],'PASS_LOCAL_COMMIT_ONLY')
        self.assertFalse(result['remote_head_authenticated'])
    def test_mismatched_content_fails(self):
        with zipfile.ZipFile(self.archive) as z:
            (self.repo/'SOURCE_SHA256.json').write_bytes(z.read('civitas-omega/SOURCE_SHA256.json'))
        self.file.write_bytes(b'wrong\n')
        call(self.repo,'add','.');call(self.repo,'commit','-m','corruption')
        result=mod.verify(self.repo,self.archive,'public',call(self.repo,'rev-parse','HEAD'))
        self.assertEqual(result['source_parity'],'FAIL')
        self.assertIn('demo.txt',[x['path'] for x in result['mismatches']])
    def test_wrong_commit_denied(self):
        with self.assertRaisesRegex(mod.VerificationError,'expected head'):
            mod.verify(self.repo,self.archive,'public','0'*40)
    def test_dirty_checkout_denied(self):
        self.file.write_bytes(b'changed')
        with self.assertRaisesRegex(mod.VerificationError,'dirty'):
            mod.verify(self.repo,self.archive,'public',self.head)
    def test_wrong_remote_denied(self):
        call(self.repo,'remote','set-url','origin','https://github.com/attacker/else.git')
        with self.assertRaisesRegex(mod.VerificationError,'origin'):
            mod.verify(self.repo,self.archive,'public',self.head)
    def test_unsafe_archive_path_rejected(self):
        self.freeze({'../escape':b'b'})
        with self.assertRaisesRegex(mod.VerificationError,'unsafe'):
            mod.checked_archive(self.archive,'public')
    def test_archive_tamper_denied(self):
        self.archive.write_bytes(self.archive.read_bytes()+b'TAMPER')
        with self.assertRaisesRegex(mod.VerificationError,'digest'):
            mod.checked_archive(self.archive,'public')
    def test_root_scope_denied(self):
        with self.assertRaisesRegex(mod.VerificationError,'checkout identity'):
            mod.verify(self.d,self.archive,'public',self.head)
if __name__=='__main__':unittest.main()
