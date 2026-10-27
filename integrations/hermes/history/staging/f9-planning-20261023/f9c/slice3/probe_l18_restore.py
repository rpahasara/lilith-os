import shutil, sys, unittest
sys.path.insert(0, r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api\tests")
from test_privacy_forget_runner import RunnerCase, R, FAREWELL, privacy, memory_v2

class Probe(RunnerCase):
    def test_probe(self):
        copy = self.root / "pre.db"
        shutil.copyfile(self.db, copy)
        self.assertEqual(self.forget().status, R.COMPLETE)
        shutil.copyfile(copy, self.db)
        v = privacy.RestoreSuppressionVerifier(self.privacy, memory_v2.L04PrivacyErasureOwner(self.db, self.privacy)).verify_and_apply()
        rows = self.fi_rows()
        print("\nverifier:", v, "\nafter restore+verify:", rows, "\nfarewell bytes present:", FAREWELL in self.db.read_bytes())

unittest.main(argv=["x"], verbosity=0)
