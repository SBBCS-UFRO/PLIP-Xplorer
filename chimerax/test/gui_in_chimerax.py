"""GUI checks: ChimeraX --exit --script '.../gui_in_chimerax.py ROOT'."""
from pathlib import Path
import sys
import time
from Qt.QtWidgets import QApplication
from chimerax.core.commands import run, StringArg
from chimerax.plip.tool import PLIPTool
from chimerax.plip.commands import plip_load

root = Path(sys.argv[1])
validation = root / 'chimerax/validation'
model = run(session, 'open ' + StringArg.unparse(str(root / 'plip/test/pdb/1vsn.pdb')))[0]
tool = PLIPTool(session)
tool.model_menu.value = model
result = plip_load(session, str(root / 'plip/test/xml/1vsn.report.xml'), model)
tool._finished(result, None)
assert tool.table.rowCount() == 13
assert tool.sites.count() == 1
tool._focus()
tool._select_contact(0, 0)
assert len(session.selection.items('atoms')) > 0
kind = 'hydrophobic_interactions'
group = result[3][('NFT:A:283', kind)]
assert group.display
tool.filters[kind].setChecked(False)
assert not group.display
assert tool.table.rowCount() < 13
tool.filters[kind].setChecked(True)
assert tool.table.rowCount() == 13
QApplication.processEvents()
tool.tool_window.ui_area.grab().save(str(validation / 'panel.png'))
run(session, 'set bgColor white')
run(session, 'save ' + StringArg.unparse(str(validation / 'binding-site.png')) + ' width 1400 height 1000')

# Exercise the actual Analyze button path and its UI-thread completion callback.
protonated = next(validation.glob('plip-*/input_protonated.pdb'))
prepared = run(session, 'open ' + StringArg.unparse(str(protonated)))[0]
tool.model_menu.value = prepared
tool.output.setText(str(validation))
tool.no_hydro.setChecked(True)
tool._analyze()
assert tool.job is not None, tool.status.text()
assert not tool.analyze.isEnabled()
deadline = time.monotonic() + 180
while tool.job is not None and time.monotonic() < deadline:
    QApplication.processEvents()
    time.sleep(0.02)
assert tool.job is None, 'GUI analysis did not finish'
assert tool.result[0].version == '3.0.1', tool.status.text()
assert tool.analyze.isEnabled()
assert not prepared.display
assert tool.result[1].display
session.models.close([model, prepared])
session.selection.clear()
tool.model_menu.value = tool.result[1]
tool._focus()
QApplication.processEvents()
tool.tool_window.ui_area.grab().save(str(validation / 'panel.png'))
run(session, 'save ' + StringArg.unparse(str(validation / 'binding-site.png')) + ' width 1400 height 1000')
run(session, 'save ' + StringArg.unparse(str(validation / 'demo-1vsn.cxs')))
(validation / 'gui-ok.txt').write_text('Panel, filters, selection, rendering and asynchronous analysis passed.\n')
tool.delete()
session.logger.info('PLIP_GUI_OK')
