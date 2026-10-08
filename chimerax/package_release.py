#!/usr/bin/env python3
"""Build a clean source + wheel ZIP for GitHub after 'devel build chimerax'."""
import hashlib
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile


ROOT_FILES = (
    'README.md', 'README_PLIP.md', 'INSTALLATION.md', 'GITHUB_RELEASE.md',
    'LICENSE.txt', 'DOCUMENTATION.md', 'CHANGES.txt', 'pyproject.toml', 'MANIFEST.in',
    '.gitignore',
)
ADAPTER_FILES = ('bundle_info.xml', 'README.md', 'VALIDATION.md', 'environment.yml',
                 'setup_backend.py', 'package_release.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    metadata = ET.parse(root / 'chimerax/bundle_info.xml').getroot()
    version = metadata.get('version')
    name = metadata.get('name').lower().replace('-', '_')
    wheel_name = f'{name}-{version}-py3-none-any.whl'
    wheel = root / 'chimerax/dist' / wheel_name
    if not wheel.is_file():
        raise SystemExit(f'Build the ChimeraX bundle first; missing {wheel}')
    files = {name: (root / name).read_bytes() for name in ROOT_FILES}
    for name in ADAPTER_FILES:
        relative = 'chimerax/' + name
        files[relative] = (root / relative).read_bytes()
    allowed = {'.py', '.pdb', '.xml', '.html', '.txt', '.sh', '.png', '.json'}
    for folder in ('plip', 'chimerax/src', 'chimerax/test'):
        for path in sorted((root / folder).rglob('*')):
            if (not path.is_file() or path.is_symlink() or '__pycache__' in path.parts
                    or path.suffix not in allowed):
                continue
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    # Reject a stale wheel instead of distributing source and installed code that differ.
    with zipfile.ZipFile(wheel) as built:
        for path in (root / 'chimerax/src').rglob('*'):
            if not path.is_file() or path.suffix not in {'.py', '.html', '.txt', '.png', '.json'}:
                continue
            relative = path.relative_to(root / 'chimerax/src').as_posix()
            if built.read('chimerax/plip/' + relative) != path.read_bytes():
                raise SystemExit(f'Wheel is out of date: {relative}. Run devel build again.')
    files['install/' + wheel_name] = wheel.read_bytes()
    manifest = ''.join(f'{digest(data)}  {path}\n' for path, data in sorted(files.items()))
    files['MANIFEST-SHA256.txt'] = manifest.encode()
    output = root / 'release'
    output.mkdir(exist_ok=True)
    install = root / 'install'
    install.mkdir(exist_ok=True)
    shutil.copyfile(wheel, install / wheel_name)
    shutil.copyfile(wheel, output / wheel_name)
    prefix = f'PLIP-Xplorer-{version}'
    archive = output / (prefix + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path, data in sorted(files.items()):
            # Stable archive entries make the same inputs reproducible.
            entry = zipfile.ZipInfo(prefix + '/' + path, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            package.writestr(entry, data)
    sums = ''.join(f'{digest(path.read_bytes())}  {path.name}\n'
                   for path in (archive, output / wheel_name))
    (output / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8')
    print(f'{archive}\n{len(files)} files; {archive.stat().st_size / 1024**2:.2f} MiB')


if __name__ == '__main__':
    main()
