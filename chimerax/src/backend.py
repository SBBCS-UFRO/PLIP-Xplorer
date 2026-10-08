"""Isolated local PLIP execution; no shell, remote services or ChimeraX imports."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


class AnalysisError(RuntimeError):
    pass


def engine_command(python, pdb_path, output, *, no_hydro=False):
    # Keep virtualenv symlinks: resolving them would launch the base interpreter.
    python = Path(python).expanduser().absolute()
    if not python.is_file():
        raise AnalysisError('Choose the Python executable of an environment containing PLIP and Open Babel.')
    args = [str(python), '-m', 'plip.plipcmd', '-f', str(Path(pdb_path).resolve()),
            '-o', str(Path(output).resolve()), '-x', '-t', '--name', 'report', '--maxthreads', '1']
    if no_hydro:
        args.append('--nohydro')
    return args


def run_engine(python, pdb_path, output, *, no_hydro=False, cancelled=lambda: False,
               timeout=600):
    """Run in a fresh output directory. Poll cancellation and keep diagnostic/provenance files."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.xml').exists():
        raise AnalysisError('The output directory already contains report.xml; use a new run directory.')
    command = engine_command(python, pdb_path, output, no_hydro=no_hydro)
    environment = os.environ.copy()
    # ChimeraX's own Python/Qt search paths must not contaminate the external interpreter.
    for name in ('PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        environment.pop(name, None)
    started = time.monotonic()
    with (output / 'engine.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(command, cwd=str(output), env=environment,
                                       stdout=log, stderr=subprocess.STDOUT)
        except OSError as err:
            raise AnalysisError(f'Cannot start PLIP: {err}') from err
        try:
            while process.poll() is None:
                if cancelled():
                    raise AnalysisError('PLIP analysis cancelled.')
                if time.monotonic() - started > timeout:
                    raise AnalysisError(f'PLIP exceeded the {timeout:g} second time limit.')
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    if cancelled():
        raise AnalysisError('PLIP analysis cancelled.')
    report = output / 'report.xml'
    if process.returncode != 0 or not report.is_file():
        tail = (output / 'engine.log').read_text(encoding='utf-8', errors='replace')[-3000:]
        raise AnalysisError(f'PLIP did not produce a report (exit {process.returncode}).\n{tail}')
    from .report import read_report
    parsed = read_report(report)
    manifest = {
        'command': command, 'plip_version': parsed.version, 'no_hydro': no_hydro,
        'input_sha256': hashlib.sha256(Path(pdb_path).read_bytes()).hexdigest(),
        'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    (output / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return parsed
