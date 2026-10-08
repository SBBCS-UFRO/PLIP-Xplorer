"""Validate generated XML for a structural corpus in a real ChimeraX session."""
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np
from chimerax.core.commands import run, StringArg
from chimerax.plip.report import KINDS

root = Path(sys.argv[1])
validation = root / 'chimerax/validation'
counts = Counter()
results = {}
for pdb in ('1eve', '3ems', '1rmd'):
    model = run(session, 'open ' + StringArg.unparse(str(root / f'plip/test/pdb/{pdb}.pdb')))[0]
    report, _, drawing, groups = run(session, 'plip load ' +
        StringArg.unparse(str(validation / pdb / 'report.xml')) + f' structure #{model.id_string}')
    num_contacts = 0
    num_segments = 0
    for site in report.sites:
        for kind in KINDS:
            contacts = [c for c in site.interactions if c.kind == kind]
            if not contacts:
                continue
            counts[kind] += len(contacts)
            num_contacts += len(contacts)
            expected = [segment for c in contacts for segment in c.segments]
            bonds = groups[(site.identifier, kind)].pseudobond_group('contacts').pseudobonds
            assert len(bonds) == len(expected)
            num_segments += len(bonds)
            for bond, (first, second) in zip(bonds, expected):
                assert np.allclose(bond.atoms[0].coord, first)
                assert np.allclose(bond.atoms[1].coord, second)
    results[pdb] = {'sites': len(report.sites), 'interactions': num_contacts, 'segments': num_segments}
    run(session, 'close all')
results['counts'] = dict(counts)
(validation / 'corpus-ok.json').write_text(json.dumps(results, indent=2))
session.logger.info('PLIP_CORPUS_OK: ' + json.dumps(results))
