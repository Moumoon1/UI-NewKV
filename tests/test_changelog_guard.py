import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_changelog.py"


class ChangelogGuardTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        (root / "CHANGELOG.md").write_text("# 更新日志\n\n## 2026-09-23\n\n- 初始化。\n")
        (root / "SKILL.md").write_text("initial\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
        return temp, root

    def run_guard(self, root):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rejects_skill_change_without_changelog(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "SKILL.md").write_text("changed\n")
        result = self.run_guard(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("CHANGELOG.md must be updated", result.stderr)

    def test_accepts_skill_change_with_changelog(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "SKILL.md").write_text("changed\n")
        with (root / "CHANGELOG.md").open("a") as handle:
            handle.write("\n- 更新规则。\n")
        result = self.run_guard(root)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
