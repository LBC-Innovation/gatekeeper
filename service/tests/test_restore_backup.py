"""gatekeeper-restore: list the backups, restore one, and never lose the ledger it replaces."""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import restore_backup as R  # noqa: E402
from gatekeeper.core import Gatekeeper  # noqa: E402


class RestoreBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "data" / "backups").mkdir(parents=True)
        self.db = self.home / "data" / "gatekeeper.db"
        gk = Gatekeeper(self.db, self.home)
        gk.set_config("profile", {"company": "Fixture Co", "urls": ["https://example.org"], "summary": "Synthetic test company.", "confirmed": True}, "test fixture setup")
        gk.close()
        self.backup = self.home / "data" / "backups" / "gatekeeper-20261001-120000.db"
        src = sqlite3.connect(self.db)
        dst = sqlite3.connect(self.backup)
        src.backup(dst)
        dst.close()
        src.close()
        gk = Gatekeeper(self.db, self.home)
        gk.start_run("manual")
        gk.finish_run(1)
        gk.close()

    def tearDown(self):
        self.tmp.cleanup()

    def runs(self):
        con = sqlite3.connect(self.db)
        try:
            return con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        finally:
            con.close()

    def test_the_list_describes_each_backup_newest_first(self):
        rows = R.list_backups(self.home)
        self.assertEqual([r["name"] for r in rows], [self.backup.name])
        self.assertEqual((rows[0]["company"], rows[0]["runs"], rows[0]["ok"]), ("Fixture Co", 0, True))

    def test_a_restore_brings_the_old_ledger_back_and_keeps_the_one_it_replaced(self):
        self.assertEqual(self.runs(), 1)
        res = R.restore(self.home, self.backup.name, echo=lambda *_: None)
        self.assertEqual(self.runs(), 0)
        kept = self.home / "data" / "backups" / res["saved_current_as"]
        self.assertTrue(kept.is_file() and "-before-restore" in kept.name)
        self.assertEqual(R.describe(kept)["runs"], 1)
        # and the restore can itself be undone
        R.restore(self.home, kept.name, echo=lambda *_: None)
        self.assertEqual(self.runs(), 1)

    def test_only_files_inside_the_backups_folder_can_be_restored(self):
        for bad in ("../gatekeeper.db", "/etc/hosts", "missing.db", "gatekeeper-20261001-120000.txt"):
            with self.assertRaises(SystemExit, msg=bad):
                R.restore(self.home, bad, echo=lambda *_: None)
        self.assertEqual(self.runs(), 1)

    def test_a_restore_is_refused_while_a_run_is_in_progress(self):
        gk = Gatekeeper(self.db, self.home)
        gk.start_run("manual")
        gk.close()
        with self.assertRaises(SystemExit) as cm:
            R.restore(self.home, self.backup.name, echo=lambda *_: None)
        self.assertIn("in progress", str(cm.exception))
        self.assertEqual(self.runs(), 2)

    def test_a_damaged_backup_is_not_restored(self):
        bad = self.home / "data" / "backups" / "gatekeeper-20261002-000000.db"
        bad.write_bytes(b"not a database")
        with self.assertRaises(SystemExit):
            R.restore(self.home, bad.name, echo=lambda *_: None)
        self.assertEqual(self.runs(), 1)


if __name__ == "__main__":
    unittest.main()
