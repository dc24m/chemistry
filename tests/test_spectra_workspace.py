import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication, QDockWidget
import spectra_app
import spectra_theme

_APP = QApplication.instance() or QApplication([])


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.window = spectra_app.MainWindow()
        self.window.show()
        _APP.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        _APP.processEvents()

    def test_one_resizable_sidebar_with_three_task_tabs(self):
        docks = self.window.findChildren(QDockWidget)
        self.assertEqual(len(docks), 1)
        self.assertEqual(docks[0].windowTitle(), 'Workspace')
        self.assertGreaterEqual(docks[0].width(), 320)
        self.assertLessEqual(docks[0].width(), 360)
        panel = self.window.controls
        self.assertLess(panel.minimumWidth(), panel.maximumWidth())
        self.assertEqual([panel.workspace_tabs.tabText(i) for i in range(3)],
                         ['Data', 'Layout', 'Style'])
        self.assertTrue(panel.workspace_pages['Data'].isAncestorOf(panel.panel_tabs))
        self.assertTrue(panel.workspace_pages['Layout'].isAncestorOf(panel.spin_fw))
        self.assertTrue(panel.workspace_pages['Style'].isAncestorOf(panel.combo_font))
        self.assertTrue(panel.workspace_pages['Style'].isAncestorOf(panel.combo_tick_dir))

    def test_sidebar_can_be_closed_and_reopened_without_losing_values(self):
        dock = self.window.dock_build
        self.window.controls.spin_lw.setValue(3.5)
        dock.close()
        self.assertFalse(dock.isVisible())
        dock.toggleViewAction().trigger()
        self.assertTrue(dock.isVisible())
        self.assertEqual(self.window.controls.spin_lw.value(), 3.5)

    def test_mode_selector_updates_controls_and_menu(self):
        self.window.header.mode_tabs.buttons['ta'].click()
        self.assertEqual(self.window.controls.current_mode(), 'ta')
        self.assertTrue(self.window.mode_actions['ta'].isChecked())
        self.assertTrue(self.window.controls.g_ta.isVisible())
        self.assertFalse(self.window.controls.g_data.isVisible())

    def test_collapsing_advanced_section_preserves_setting(self):
        panel = self.window.controls
        panel.workspace_tabs.setCurrentIndex(2)
        section = panel.sections['Ticks']
        self.assertFalse(section.content.isVisible())
        section.toggle.click()
        self.assertTrue(section.content.isVisible())
        panel.spin_tick_len.setValue(7.5)
        section.toggle.click()
        section.toggle.click()
        self.assertEqual(panel.spin_tick_len.value(), 7.5)

    def test_section_titles_escape_button_mnemonics(self):
        # 'Files & traces' must not render as 'Files_traces'.
        self.assertEqual(self.window.controls.g_data.toggle.text(), 'Files && traces')
        self.assertEqual(self.window.controls.sections['Files & traces'], self.window.controls.g_data)

    def test_restore_data_backfills_reference_scale_and_offset(self):
        panel = self.window.controls
        panel.restore_data({'xrd_refs': ['a.xy', 'b.xy'], 'xrd_ref_colors': ['#000000']})
        self.assertEqual(panel.xrd_ref_scales, [1.0, 1.0])
        self.assertEqual(panel.xrd_ref_offsets, [0.0, 0.0])
        self.assertEqual(panel.capture_data()['xrd_ref_scales'], [1.0, 1.0])
        self.assertEqual(panel.settings()['xrd_ref_offsets'], [0.0, 0.0])

    def test_show_legend_off_greys_out_legend_controls(self):
        panel = self.window.controls
        others = (panel.combo_legend_loc, panel.spin_legend_fs, panel.chk_legend_2col,
                  panel.chk_legend_transp_bg, panel.color_legend_edge)
        self.assertTrue(all(w.isEnabled() for w in others))
        panel.chk_legend.setChecked(False)
        self.assertFalse(any(w.isEnabled() for w in others))
        self.assertTrue(panel.chk_legend.isEnabled())
        panel.chk_legend.setChecked(True)
        self.assertTrue(all(w.isEnabled() for w in others))
        self.assertFalse(panel.color_legend_bg.isEnabled())  # transparent BG still wins
        panel._apply_style_preset({'show_legend': False})
        self.assertFalse(panel.spin_legend_fs.isEnabled())

    def test_header_actions_have_named_signals(self):
        header = spectra_app.TopHeader()
        for name in ('presets', 'open', 'save', 'export'):
            seen = []
            getattr(header, name + '_requested').connect(lambda: seen.append(True))
            getattr(header, 'btn_' + name).click()
            self.assertEqual(seen, [True])

    def test_ui_scale_uses_qt_logical_pixels(self):
        self.assertEqual(spectra_theme.init_ui_scale(_APP), 1.0)
        self.assertEqual(spectra_theme.s(340), 340)
        self.assertEqual(spectra_theme.vs(8), 8)


if __name__ == '__main__':
    unittest.main()
