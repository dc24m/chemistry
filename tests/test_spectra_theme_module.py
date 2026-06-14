# tests/test_spectra_theme_module.py
import unittest


class ThemeModuleTest(unittest.TestCase):
    def test_theme_module_owns_build_style_and_modes(self):
        import spectra_theme
        self.assertTrue(hasattr(spectra_theme, "build_style"))
        self.assertTrue(hasattr(spectra_theme, "MODES"))
        self.assertEqual(spectra_theme.MODES[0]["key"], "pl")

    def test_spectra_app_reexports_theme_symbols(self):
        import spectra_app
        import spectra_theme
        self.assertIs(spectra_app.build_style, spectra_theme.build_style)
        self.assertIs(spectra_app.MODES, spectra_theme.MODES)

    def test_build_style_accepts_accent_and_dark_flag(self):
        import spectra_theme
        light = spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        dark = spectra_theme.build_style(spectra_theme.MODES[0]["accent"], dark=True)
        self.assertIn("QMainWindow", light)
        self.assertNotEqual(light, dark)

    def test_build_style_reuses_cached_stylesheets(self):
        import spectra_theme
        spectra_theme.build_style.cache_clear()

        spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        before = spectra_theme.build_style.cache_info()
        spectra_theme.build_style(spectra_theme.MODES[0]["accent"])
        after = spectra_theme.build_style.cache_info()

        self.assertEqual(after.hits, before.hits + 1)
        self.assertEqual(after.misses, before.misses)


if __name__ == "__main__":
    unittest.main()
