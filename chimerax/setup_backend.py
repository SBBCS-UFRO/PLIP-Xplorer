#!/usr/bin/env python3
"""Create a separate PLIP environment. Requires an existing Conda/Miniforge install."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conda', default=os.environ.get('CONDA_EXE') or shutil.which('conda'))
    parser.add_argument('--prefix', type=Path, default=root / '.plip-env')
    args = parser.parse_args()
    if not args.conda:
        parser.error('Install Miniforge first, or provide --conda /path/to/conda.')
    prefix = args.prefix.expanduser().absolute()
    if prefix.exists():
        parser.error(f'{prefix} already exists. Choose a new --prefix to avoid modifying an existing environment.')
    subprocess.run([args.conda, 'env', 'create', '--prefix', str(prefix), '--file',
                    str(root / 'chimerax/environment.yml'), '--yes'], check=True)
    python = prefix / ('python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', str(root)], check=True)
    subprocess.run([str(python), '-c', 'from plip.structure.preparation import PDBComplex; '
                    'from openbabel import openbabel; print("Open Babel", openbabel.OBReleaseVersion())'], check=True)
    # A portable .cxc file avoids requiring users to retype platform-specific paths.
    config = prefix / 'configure-chimerax.cxc'
    config.write_text('plip settings python ' + json.dumps(str(python), ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'PLIP is ready. After installing the ChimeraX bundle, open this file in ChimeraX:\n{config}')


if __name__ == '__main__':
    main()
