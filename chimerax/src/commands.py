"""Commands shared by the Qt tool and ChimeraX scripts."""
from pathlib import Path
import tempfile

from chimerax.core.errors import UserError
from .settings import get_settings


def plip_settings(session, python=None):
    settings = get_settings(session)
    if python is not None:
        path = Path(python).expanduser().absolute()
        if not path.is_file():
            raise UserError(f'Python executable not found: {path}')
        settings.python = str(path)
    session.logger.info(f'PLIP Python: {settings.python or "not configured"}')
    return settings.python


def prepare_analysis(session, structure, python=None, output=None):
    from chimerax.pdb import save_pdb
    from .backend import engine_command
    python = python or get_settings(session).python
    if not python:
        raise UserError('Configure the PLIP Python executable in Tools → Structure Analysis → PLIP-Xplorer '
                        'or with plip settings python /path/to/python.')
    # Fail explicitly instead of silently truncating mmCIF identifiers into PDB columns.
    if structure.num_atoms > 99999:
        raise UserError('This PLIP adapter supports at most 99,999 atoms per PDB snapshot.')
    for residue in structure.residues:
        if len(residue.chain_id.strip()) > 1 or not -999 <= residue.number <= 9999:
            raise UserError('The model has chain IDs or residue numbers outside PDB limits. '
                            'Rename chains/renumber residues on a copy before analysis.')
    base = Path(output).expanduser().resolve() if output else None
    if base:
        base.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='plip-', dir=base))
    path = directory / 'input.pdb'
    engine_command(python, path, directory)
    save_pdb(session, str(path), models=[structure], rel_model=structure, all_coordsets=False)
    return python, directory, structure.scene_position


def show_results(session, report, directory, position):
    from chimerax.atomic import AtomicStructure
    from .visualize import draw_report, style_site
    models, _ = session.open_command.open_data(str(directory / 'input.pdb'), format='pdb')
    if len(models) != 1 or not isinstance(models[0], AtomicStructure):
        for model in models:
            model.delete()
        raise UserError('Expected one atomic structure in the exported PDB snapshot.')
    model = models[0]
    model.name = 'PLIP-Xplorer analyzed snapshot'
    model.position = position
    try:
        root, groups = draw_report(session, report, model)
        session.models.add([model])
        if report.sites:
            style_site(session, model, report.sites[0])
            for (site, _), group in groups.items():
                group.display = site == report.sites[0].identifier
    except Exception:
        model.delete()
        raise
    count = sum(len(s.interactions) for s in report.sites)
    session.logger.info(f'PLIP {report.version}: {len(report.sites)} binding site(s), '
                        f'{count} interactions. Reports: {directory}')
    if not report.sites:
        session.logger.warning('PLIP found no eligible ligands. Check ligand identities and PLIP exclusions.')
    return report, model, root, groups


def plip_analyze(session, structures, python=None, output=None, no_hydro=False, wait=None):
    if len(structures) != 1:
        raise UserError('Choose exactly one atomic model for PLIP analysis.')
    from .backend import run_engine
    try:
        python, directory, position = prepare_analysis(session, structures[0], python, output)
        if wait is True or not session.ui.is_gui:
            report = run_engine(python, directory / 'input.pdb', directory, no_hydro=no_hydro)
            result = show_results(session, report, directory, position)
            structures[0].display = False
            return result
        from .job import AnalysisJob
        job = AnalysisJob(session, python, directory, position, no_hydro, source=structures[0])
        job.start()
        session.logger.info(f'PLIP analysis started; reports will be saved in {directory}')
        return job
    except (OSError, ValueError, RuntimeError) as err:
        raise UserError(str(err)) from err


def plip_load(session, report, structure):
    from .report import read_report
    from .visualize import draw_report
    try:
        parsed = read_report(report)
        root, groups = draw_report(session, parsed, structure)
    except (OSError, ValueError) as err:
        raise UserError(str(err)) from err
    session.logger.info(f'Loaded PLIP {parsed.version}: {len(parsed.sites)} binding site(s).')
    return parsed, structure, root, groups


def register_command(name, logger):
    from chimerax.core.commands import CmdDesc, register, StringArg, BoolArg, OpenFileNameArg, SaveFolderNameArg
    from chimerax.atomic import AtomicStructuresArg, AtomicStructureArg
    if name == 'plip analyze':
        desc = CmdDesc(required=[('structures', AtomicStructuresArg)], keyword=[
            ('python', OpenFileNameArg), ('output', SaveFolderNameArg),
            ('no_hydro', BoolArg), ('wait', BoolArg)], synopsis='Analyze one model using PLIP')
        function = plip_analyze
    elif name == 'plip load':
        desc = CmdDesc(required=[('report', OpenFileNameArg)],
                       required_arguments=['structure'], keyword=[('structure', AtomicStructureArg)],
                       synopsis='Display a PLIP XML report on its matching structure')
        function = plip_load
    else:
        desc = CmdDesc(keyword=[('python', StringArg)], synopsis='Configure the PLIP Python executable')
        function = plip_settings
    register(name, desc, function, logger=logger)
