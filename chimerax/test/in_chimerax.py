"""Run with ChimeraX --nogui --exit --script '.../in_chimerax.py ROOT PYTHON'."""
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

from chimerax.core.commands import run, StringArg
from chimerax.atomic import AtomicStructure
from chimerax.geometry import translation
from chimerax.plip.report import read_report
from chimerax.plip.visualize import draw_report, validate_coordinates


root = Path(sys.argv[1])
python = sys.argv[2]
output = root / 'chimerax' / 'validation'
output.mkdir(exist_ok=True)
quote = StringArg.unparse
models = run(session, 'open ' + quote(str(root / 'plip/test/pdb/1vsn.pdb')))
source = next(m for m in models if isinstance(m, AtomicStructure))
source.position = translation((8, 12, -3))
run(session, 'plip settings python ' + quote(python))
result = run(session, f'plip analyze #{source.id_string} output {quote(str(output))} wait true')
report, model, drawing, groups = result
assert model != source and not source.deleted
assert model.scene_position == source.scene_position
assert report.version == '3.0.1'
assert report.sites[0].identifier == 'NFT:A:283'
assert len(report.sites[0].interactions) > 0

# Compare all rendered segment counts and positions directly to PLIP's XML output.
expected = sum(len(c.segments) for site in report.sites for c in site.interactions)
actual = sum(g.pseudobond_group('contacts').num_pseudobonds for g in groups.values())
assert actual == expected, (actual, expected)
for site in report.sites:
    for kind in {c.kind for c in site.interactions}:
        segments = [p for c in site.interactions if c.kind == kind for p in c.segments]
        pbonds = groups[(site.identifier, kind)].pseudobond_group('contacts').pseudobonds
        for bond, (first, second) in zip(pbonds, segments):
            import numpy as np
            assert np.allclose(bond.atoms[0].coord, first)
            assert np.allclose(bond.atoms[1].coord, second)

# Drawings inherit rigid model movement, and mismatched coordinates fail before drawing.
old_position = next(iter(groups.values())).scene_position
model.position = translation((20, 30, 40))
assert next(iter(groups.values())).scene_position != old_position
model.atoms.coords += 100
try:
    validate_coordinates(report, model)
except ValueError:
    pass
else:
    raise AssertionError('Mismatched model should have been rejected')
model.atoms.coords -= 100

# Round trip native models through a ChimeraX session, not an adapter-specific serializer.
scene = output / 'smoke.cxs'
run(session, 'save ' + quote(str(scene)))
run(session, 'close all')
run(session, 'open ' + quote(str(scene)))
from chimerax.markers import MarkerSet
restored = session.models.list(type=MarkerSet)
assert sum(m.pseudobond_group('contacts').num_pseudobonds for m in restored) == expected
session.logger.info(f'PLIP_SMOKE_OK: {len(report.sites[0].interactions)} interactions; '
                    f'{expected} segments; session round trip passed.')
(output / 'smoke-ok.txt').write_text(f'{len(report.sites[0].interactions)} interactions, {expected} segments\n')
