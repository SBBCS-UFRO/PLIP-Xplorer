"""Verify the installed name, existing preferences and a pre-rename session."""
from pathlib import Path
import json
import sys
import traceback

root = Path(sys.argv[1])
output = root / 'chimerax/validation'
output.mkdir(exist_ok=True)


def check():
    from chimerax.core.commands import run, StringArg
    from chimerax.plip.settings import get_settings
    from chimerax.plip.tool import PLIPTool
    bundles = session.toolshed.bundle_info(session.logger, installed=True, available=False)
    names = {bundle.name for bundle in bundles}
    assert 'ChimeraX-PLIP-Xplorer' in names
    assert not {'ChimeraX-PLIP', 'ChimeraX-PLIP-Explorer'} & names, 'Legacy distributions are installed'
    bundle = next(b for b in bundles if b.name == 'ChimeraX-PLIP-Xplorer')
    assert str(bundle.version) == '1.0.0'
    assert [t.name for t in bundle.tools] == ['PLIP-Xplorer']
    python = get_settings(session).python
    assert python and Path(python).is_file(), 'Existing Python setting was not retained'
    run(session, 'ui tool show PLIP-Xplorer')
    tool = next(t for t in session.tools.list() if isinstance(t, PLIPTool))
    assert tool.tool_name == 'PLIP-Xplorer'
    assert tool.help == 'help:user/tools/plip-xplorer.html'
    old_session = root / 'chimerax/validation/custom-publication.cxs'
    assert old_session.is_file(), 'Generate the 0.2 example session before this migration check'
    run(session, 'open ' + StringArg.unparse(str(old_session)))
    assert session.models.list(), 'The existing scene did not restore'
    # Command registration still works after the package rename.
    assert run(session, 'plip settings') == python
    return {'status': 'passed', 'bundle': bundle.name, 'version': str(bundle.version),
            'tool': 'PLIP-Xplorer', 'previous_preferences': 'retained',
            'previous_session': 'restored', 'commands': 'plip settings works'}


try:
    result = check()
    (output / 'rename-check.json').write_text(json.dumps(result, indent=2))
except Exception:
    (output / 'rename-check.json').write_text(traceback.format_exc())
    raise
