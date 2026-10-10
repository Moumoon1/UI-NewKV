from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_figma_commit_js import build


class CommitGeneratorTests(unittest.TestCase):
    def test_guards_and_exact_cleanup_are_emitted(self):
        with tempfile.TemporaryDirectory() as directory:
            apply_js = Path(directory) / 'apply.js'
            apply_js.write_text('async function applyThemeWriteToClone(){return {status:"pass"}}')
            program = build('source', 'fingerprint', 'plan', apply_js,
                            expected_nodes=1006, expected_receipt={'kvLocked': True},
                            delivery_name='ui · L-D 换肤')
        self.assertIn('source fingerprint changed', program)
        self.assertIn('temporary preview remains', program)
        self.assertIn('rightEdge+256', program)
        self.assertIn('write receipt mismatch', program)
        self.assertIn('clone.remove()', program)
        self.assertIn('source changed during delivery', program)


if __name__ == '__main__':
    unittest.main()
