import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar

import spectra_app


class LoadingScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_loading_screen_has_status_and_indeterminate_progress(self):
        splash = spectra_app.create_loading_screen()

        self.assertEqual(splash.objectName(), "loadingScreen")

        status = splash.findChild(QLabel, "loadingStatus")
        self.assertIsNotNone(status)
        self.assertIn("Preparing plotting workspace", status.text())

        progress = splash.findChild(QProgressBar, "loadingProgress")
        self.assertIsNotNone(progress)
        self.assertEqual(progress.minimum(), 0)
        self.assertEqual(progress.maximum(), 0)


if __name__ == "__main__":
    unittest.main()
