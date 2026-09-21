import os
import shutil
import tempfile
import time
import unittest

from agents.reasoning_agent import prune_screenshots


class ScreenshotPruningTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _make(self, name, age, is_dir=True):
        path = os.path.join(self.root, name)
        if is_dir:
            os.makedirs(path)
            open(os.path.join(path, "001_iteration.png"), "wb").close()
        else:
            open(path, "wb").close()
        past = time.time() - age
        os.utime(path, (past, past))
        return path

    def test_only_the_newest_runs_are_kept(self):
        newest = self._make("run-new", age=10)
        middle = self._make("run-mid", age=100)
        oldest = self._make("run-old", age=1000)
        loose = self._make("iteration_1700000000.png", age=5000, is_dir=False)

        removed = prune_screenshots(self.root, keep=2)

        self.assertEqual(removed, 2)
        self.assertTrue(os.path.exists(newest) and os.path.exists(middle))
        self.assertFalse(os.path.exists(oldest) or os.path.exists(loose))

    def test_other_files_such_as_the_readme_are_never_removed(self):
        readme = self._make("README.md", age=99999, is_dir=False)
        self._make("run-a", age=10)

        prune_screenshots(self.root, keep=0)

        self.assertTrue(os.path.exists(readme))

    def test_missing_folder_is_fine(self):
        self.assertEqual(prune_screenshots(os.path.join(self.root, "absent"), keep=1), 0)


if __name__ == "__main__":
    unittest.main()
