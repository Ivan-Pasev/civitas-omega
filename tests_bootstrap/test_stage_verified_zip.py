"""Offline guardrail tests for the import boundary only, not CIVITAS runtime."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "stage_verified_zip.py"
spec = importlib.util.spec_from_file_location("stage_verified_zip", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def package(entries, root="civitas-omega"):
    manifest = {k: hashlib.sha256(v).hexdigest() for k,v in entries.items()}
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path,content in entries.items():
            z.writestr(root + "/" + path,content)
        z.writestr(root + "/SOURCE_SHA256.json",json.dumps({"files":manifest}))
    return data.getvalue()

class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive = Path(self.tmp.name) / "sample.zip"
        self.candidate = mod.CANDIDATES["public"]
        self.addCleanup(lambda: mod.CANDIDATES.__setitem__("public", self.candidate))
    def configure(self, payload, count):
        self.archive.write_bytes(payload)
        mod.CANDIDATES["public"] = (self.archive.name, hashlib.sha256(payload).hexdigest(), "civitas-omega",count)
    def test_good_manifest(self):
        self.configure(package({"hello.txt":b"ok"}),2)
        self.assertEqual(mod.read_checked(self.archive,"public")["hello.txt"],b"ok")
    def test_mismatched_archive_hash(self):
        self.configure(package({"hello.txt":b"ok"}),2)
        self.archive.write_bytes(self.archive.read_bytes()+b"tamper")
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
            mod.read_checked(self.archive,"public")
    def test_parent_traversal(self):
        self.configure(package({"../bad.txt":b"x"}),2)
        with self.assertRaisesRegex(ValueError,"invalid path"):
            mod.read_checked(self.archive,"public")
    def test_duplicate_member(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('civitas-omega/a.txt',b'a')
            z.writestr('civitas-omega/a.txt',b'b')
            z.writestr('civitas-omega/SOURCE_SHA256.json',json.dumps({'files':{'a.txt':hashlib.sha256(b'b').hexdigest()}}))
        self.configure(data.getvalue(),3)
        with self.assertRaisesRegex(ValueError,"duplicate member"):
            mod.read_checked(self.archive,"public")
    def test_reject_wrong_scope(self):
        self.configure(package({"hello.txt":b"ok"},root='civitas-omega-lab'),2)
        with self.assertRaisesRegex(ValueError,"invalid path"):
            mod.read_checked(self.archive,"public")
    def test_never_stage_into_wrong_repo_name(self):
        self.configure(package({"hello.txt":b"ok"}),2)
        checkout=Path(self.tmp.name)/'something-else';checkout.mkdir();(checkout/'.git').mkdir()
        with self.assertRaisesRegex(ValueError,"checkout must be"):
            mod.main(['--scope','public','--archive',str(self.archive),'--checkout',str(checkout),'--apply'])
        self.assertFalse((checkout/'hello.txt').exists())

if __name__ == '__main__':
    unittest.main()
