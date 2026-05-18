from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MigrationFileTests(unittest.TestCase):
    def test_alembic_file_hash_migration_is_declared(self):
        self.assertTrue((ROOT / "alembic.ini").exists())
        self.assertTrue((ROOT / "alembic" / "env.py").exists())

        versions_dir = ROOT / "alembic" / "versions"
        migrations = list(versions_dir.glob("*add_file_hash_to_log_upload.py"))
        self.assertEqual(len(migrations), 1)

        migration = migrations[0].read_text(encoding="utf-8")
        self.assertIn("file_hash", migration)
        self.assertIn("ix_log_upload_file_hash", migration)
        self.assertIn("ux_log_upload_success_file_hash", migration)
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS", migration)

    def test_requirements_declares_alembic_dependency(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        self.assertIn("alembic==", requirements)


if __name__ == "__main__":
    unittest.main()
