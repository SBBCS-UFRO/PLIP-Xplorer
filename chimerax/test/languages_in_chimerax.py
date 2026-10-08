"""Exercise every locale in the real GUI, including scientific-state preservation."""
import json
from pathlib import Path
import sys
import traceback

root = Path(sys.argv[1])
out = root / 'chimerax/validation'
out.mkdir(exist_ok=True)


def check():
    from Qt.QtWidgets import QApplication, QLabel, QPushButton, QGroupBox
    from chimerax.core.commands import run, StringArg
    from chimerax.plip.tool import PLIPTool
    from chimerax.plip.commands import plip_load
    from chimerax.plip.settings import get_settings
    from chimerax.plip.i18n import LANGUAGES, TITLE, COPYRIGHT, catalog
    from chimerax.plip.appearance import preset_style
    from chimerax.label.label3d import ObjectLabels
    settings = get_settings(session)
    original_language = settings.language
    tool = None
    try:
        model = run(session, 'open ' + StringArg.unparse(str(root / 'plip/test/pdb/1vsn.pdb')))[0]
        result = plip_load(session, str(root / 'plip/test/xml/1vsn.report.xml'), model)
        tool = PLIPTool(session)
        tool._finished(result, None)
        assert tool.display_name == TITLE
        assert not tool.logo.pixmap().isNull()
        assert tool.credit.text() == COPYRIGHT
        style = preset_style('Publication')
        tool.appearance.set_style(style)
        tool.filters['hydrophobic_interactions'].setChecked(False)
        count = tool.table.rowCount()
        expected_style = tool.appearance.style()
        rows_before = [repr(c) for c in tool._rows]
        camera = session.main_view.camera.position
        # Mark a label offset so language switches must preserve manual placement.
        models_before = session.models.list(type=ObjectLabels)
        selected_label = next(iter(models_before[0].labels()))
        selected_label.offset = (1.23, 2.34, 3.45)
        for code in LANGUAGES:
            tool.language_menu.setCurrentIndex(tool.language_menu.findData(code))
            QApplication.processEvents()
            assert tool.analyze.text() == tool.tr('Analyze structure')
            assert tool.tabs.tabText(1) == tool.tr('Appearance')
            assert tool.table.horizontalHeaderItem(0).text() == tool.tr('Interaction')
            assert settings.language == code
            assert tool.appearance.style() == expected_style
            assert tool.table.rowCount() == count
            assert [repr(c) for c in tool._rows] == rows_before
            assert session.main_view.camera.position == camera
            assert session.models.list(type=ObjectLabels) == models_before
            assert tuple(selected_label.offset) == (1.23, 2.34, 3.45)
            assert not tool.filters['hydrophobic_interactions'].isChecked()
            tool.appearance.set_style(json.loads(json.dumps(expected_style)), apply=False)
            assert tool.appearance.style() == expected_style
            assert tool.appearance.controls['camera'].currentData() == expected_style['camera']
            # Known static strings should never remain in English by accident.
            if code != 'en':
                for w in tool.tool_window.ui_area.findChildren(QLabel):
                    if w.text() in catalog('en'):
                        assert catalog(code)[w.text()] == w.text(), (code, w.text())
            tool.language.message(tool.status, 'Analyzing with PLIP… Results: {directory}', directory='/tmp/{input}/α')
            assert '/tmp/{input}/α' in tool.status.text()
            tool.tool_window.ui_area.grab().save(str(out / f'language-{code}.png'))
        # New panels restore the preferred language. Unknown saved locales fall back.
        other = PLIPTool(session)
        assert other.language.code == 'pt'
        assert other.analyze.text() == other.tr('Analyze structure')
        other.delete()
        tool.language_menu.setCurrentIndex(tool.language_menu.findData('es'))
        tool.appearance.preset.setCurrentIndex(tool.appearance.preset.findData('Dark presentation'))
        apply_button = next(w for w in tool.appearance.widget.findChildren(QPushButton)
                            if w.text() == tool.tr('Apply preset'))
        apply_button.click()
        assert tool.appearance.style()['background'] == preset_style('Dark presentation')['background']
        assert tool.appearance.controls['lighting'].currentData() == 'full'
        assert tool.result is result
        tool.tabs.setCurrentIndex(1)
        QApplication.processEvents()
        tool.tool_window.ui_area.grab().save(str(out / 'language-es-appearance.png'))
        tool.tabs.setCurrentIndex(2)
        QApplication.processEvents()
        tool.tool_window.ui_area.grab().save(str(out / 'language-es-export.png'))
        return {'status': 'passed', 'languages': list(LANGUAGES), 'title': TITLE,
                'logo': 'loaded', 'credit': COPYRIGHT,
                'style_roundtrip': 'all languages', 'manual_labels': 'preserved',
                'scientific_results': 'unchanged', 'preference': 'retained'}
    finally:
        if tool is not None:
            tool.delete()
        settings.language = original_language


try:
    (out / 'languages-check.json').write_text(json.dumps(check(), ensure_ascii=False, indent=2), encoding="utf-8")
except Exception:
    (out / 'languages-check.json').write_text(traceback.format_exc(), encoding="utf-8")
    raise
