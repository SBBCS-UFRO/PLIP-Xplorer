"""Real GUI/rendering regression test for PLIP appearance and image export."""
import json
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

root = Path(sys.argv[1])
out = root / 'chimerax/validation'


def check():
    import numpy as np
    from PIL import Image
    from Qt.QtWidgets import QApplication
    from chimerax.core.commands import run, StringArg
    from chimerax.plip.tool import PLIPTool
    from chimerax.plip.commands import plip_load
    from chimerax.plip.appearance import preset_style, export_image, apply_scene
    from chimerax.label.label3d import ObjectLabels
    quote = StringArg.unparse
    model = run(session, 'open ' + quote(str(root / 'plip/test/pdb/1vsn.pdb')))[0]
    other = run(session, 'open ' + quote(str(root / 'plip/test/pdb/1rmd.pdb')))[0]
    result = plip_load(session, str(root / 'plip/test/xml/1vsn.report.xml'), model)
    tool = PLIPTool(session)
    tool._finished(result, None)
    tool._focus()
    panel = tool.appearance
    original_mouse_mode = session.ui.mouse_modes.mode('right', exact=True)
    panel.move_labels.setChecked(True)
    assert session.ui.mouse_modes.mode('right', exact=True).name == 'move label'
    panel.move_labels.setChecked(False)
    assert session.ui.mouse_modes.mode('right', exact=True) is original_mouse_mode
    before = model.atoms.coords.copy()
    data_before = repr(result[0])
    style = preset_style('Publication')
    panel.set_style(style)
    apply_scene(session, panel.style())
    session.main_view.camera.field_of_view = 35
    panel.apply()
    assert session.main_view.camera.field_of_view == 35
    panel.apply_result()  # Do not let the UI error handler hide a test failure.
    assert not tool.status.text().startswith('Appearance:'), tool.status.text()
    assert np.array_equal(model.atoms.coords, before)
    assert repr(result[0]) == data_before
    labels = session.models.list(type=ObjectLabels)
    assert len(labels) >= 3, len(labels)
    count = len(labels)
    panel.apply_result()
    assert len(session.models.list(type=ObjectLabels)) == count, 'Duplicate labels'
    camera = session.main_view.camera.position
    tool.filters['hydrogen_bonds'].setChecked(False)
    assert session.main_view.camera.position == camera, 'Style changed the camera'
    group = result[3][('NFT:A:283', 'hydrogen_bonds')]
    assert not group.display
    tool.filters['hydrogen_bonds'].setChecked(True)
    style['contacts']['hydrogen_bonds'].update(color='#ff0055', radius=0.15, dashes=0)
    panel.set_style(style)
    bonds = group.pseudobond_group('contacts')
    assert bonds.dashes == 0, (bonds.dashes, tool.status.text())
    assert np.allclose(bonds.pseudobonds.radii, 0.15)
    assert tuple(bonds.pseudobonds.colors[0]) == (255, 0, 85, 255)
    # Invalid settings cannot partially change the controls.
    before_style = panel.style()
    try:
        panel.set_style(dict(background='#ff0000', lighting='not a preset'))
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid preset accepted')
    assert panel.style() == before_style
    # Export must isolate other models and restore them even if the renderer fails.
    def fail(*args, **kwargs):
        assert not other.display, 'Other structure was not isolated'
        assert model.display and result[2].display
        raise RuntimeError('test renderer failure')
    with patch('chimerax.image_formats.save.save_image', side_effect=fail):
        try:
            export_image(session, result, out / 'should-not-exist.png', width=800, height=600)
        except RuntimeError as err:
            assert str(err) == 'test renderer failure'
    assert other.display and model.display
    panel.width.setValue(1000)
    panel.height.setValue(750)
    panel.aspect.setChecked(False)
    panel.supersample.setValue(1)
    panel.transparent.setChecked(True)
    panel.export_to(out / 'custom-transparent.png')
    im = Image.open(out / 'custom-transparent.png')
    assert im.size == (1000, 750)
    assert im.mode == 'RGBA' and im.getextrema()[-1][0] == 0
    assert other.display
    panel.transparent.setChecked(False)
    panel.export_to(out / 'custom-white.png')
    panel.export_to(out / 'custom-white.tiff')
    panel.image_format.setCurrentText('JPEG')
    assert not panel.transparent.isChecked() and not panel.transparent.isEnabled()
    panel.export_to(out / 'custom-white.jpg')
    for extension in ('png', 'tiff', 'jpg'):
        assert Image.open(out / f'custom-white.{extension}').size == (1000, 750)
    # The orthographic mode, optional dots and all molecular representations work.
    varied = preset_style('Original')
    varied.update(camera='ortho', markers=False, ligand_style='spheres', receptor_style='balls')
    panel.set_style(varied)
    panel.apply_result()
    assert session.main_view.camera.name == 'orthographic' or session.main_view.camera.name == 'ortho'
    panel.export_to(out / 'custom-spheres.png')
    panel.set_style(preset_style('Dark presentation'))
    panel.export_to(out / 'custom-dark.png')
    panel.set_style(preset_style('Illustration'))
    panel.export_to(out / 'custom-illustration.png')
    # Focus preserves the chosen presentation and custom preferences round-trip as JSON.
    style = preset_style('Publication')
    panel.set_style(style)
    tool._focus()
    assert not np.any(model.residues.ribbon_displays)
    saved = json.loads(json.dumps(panel.style()))
    panel.set_style(saved)
    assert panel.style() == saved
    tool.tabs.setCurrentIndex(1)
    QApplication.processEvents()
    tool.tool_window.ui_area.grab().save(str(out / 'appearance-panel.png'))
    session.models.close([other])
    run(session, 'save ' + quote(str(out / 'custom-publication.cxs')))
    tool.delete()
    count = len(session.models.list(type=ObjectLabels))
    run(session, 'close all')
    run(session, 'open ' + quote(str(out / 'custom-publication.cxs')))
    assert len(session.models.list(type=ObjectLabels)) == count, 'Labels lost on session restore'
    return {'status': 'passed', 'label_models_restored': count,
            'exports': ['transparent PNG', 'opaque PNG', 'TIFF', 'JPEG', 'dark', 'illustration']}


try:
    (out / 'appearance-check.json').write_text(json.dumps(check(), indent=2))
except Exception:
    (out / 'appearance-check.json').write_text(traceback.format_exc())
    raise
