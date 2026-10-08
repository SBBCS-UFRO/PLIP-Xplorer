"""Native, session-saveable ChimeraX models using the exact PLIP report coordinates."""
from .report import KINDS


def validate_coordinates(report, structure):
    """Reject reports in a different coordinate frame before creating any drawings.

    Aromatic/charged-group centroids are deliberately excluded: they are not atoms.
    No PDB serial-number equivalence is assumed after PLIP's structure preparation.
    """
    import numpy as np
    coords = structure.atoms.coords
    if len(coords) == 0:
        raise ValueError('The model has no atoms.')
    centroid_kinds = {'salt_bridges', 'pi_stacks', 'pi_cation_interactions'}
    for site in report.sites:
        for contact in site.interactions:
            if contact.kind in centroid_kinds:
                continue
            for point in contact.points:
                if np.min(np.sum((coords - point) ** 2, axis=1)) > 0.03 ** 2:
                    raise ValueError('Report coordinates do not match this model. Open the PDB used '
                                     'by PLIP, or analyze the model again.')


def site_residues(structure, site, include_contacts=True):
    identifiers = set()
    for member in site.members:
        parts = member.split(':')
        if len(parts) == 3:
            identifiers.add(tuple(parts))
    if include_contacts:
        identifiers.update(contact.residue for contact in site.interactions)
    return [r for r in structure.residues
            if (r.name, r.chain_id.strip(), str(r.number) + r.insertion_code.strip()) in identifiers
            or (r.name, r.chain_id.strip(), str(r.number)) in identifiers]


def draw_report(session, report, structure):
    from chimerax.core.models import Model
    from chimerax.markers import MarkerSet
    validate_coordinates(report, structure)
    root = Model(f'PLIP-Xplorer · PLIP {report.version}', session)
    groups = {}
    try:
        for site in report.sites:
            site_model = Model(site.identifier, session)
            root.add([site_model])
            for kind, (label, color) in KINDS.items():
                contacts = [c for c in site.interactions if c.kind == kind]
                if not contacts:
                    continue
                markers = MarkerSet(session, name=f'{label} ({len(contacts)})')
                site_model.add([markers])
                bonds = markers.pseudobond_group('contacts')
                bonds.dashes = 6
                for contact in contacts:
                    # Water bridges are two segments through the water oxygen; pi/salt
                    # endpoints are the group centres reported by PLIP, never nearest atoms.
                    atoms = [markers.create_marker(p, color, 0.08) for p in contact.points]
                    for first, second in zip(atoms, atoms[1:]):
                        bond = bonds.new_pseudobond(first, second)
                        bond.color = color
                        bond.halfbond = False
                        bond.radius = 0.055 if kind == 'hydrophobic_interactions' else 0.08
                groups[(site.identifier, kind)] = markers
        # Child models inherit rigid motion of their analyzed structure.
        structure.add([root])
    except Exception:
        root.delete()
        raise
    return root, groups


def style_site(session, structure, site, focus=True):
    """A local binding-site view; only the analyzed structure is styled."""
    from chimerax.atomic import Atoms
    structure.atoms.displays = False
    structure.residues.ribbon_displays = True
    structure.residues.ribbon_colors = (140, 155, 175, 65)
    residues = site_residues(structure, site)
    ligand = set(site_residues(structure, site, include_contacts=False))
    for residue in residues:
        residue.atoms.displays = True
        residue.ribbon_hide_backbone = False
        residue.atoms.draw_modes = residue.atoms[0].STICK_STYLE
        for atom in residue.atoms:
            if atom.element.name == 'C':
                atom.color = (245, 160, 45, 255) if residue in ligand else (115, 165, 215, 255)
    # Keep bridging waters/metal partners visible even if not in receptor residue fields.
    import numpy as np
    coords = structure.atoms.coords
    for contact in site.interactions:
        if contact.kind in {'water_bridges', 'metal_complexes'}:
            for point in contact.points:
                nearby = structure.atoms.filter(np.sum((coords - point) ** 2, axis=1) < 0.03 ** 2)
                nearby.displays = True
    if residues and focus:
        atoms = Atoms([a for r in residues for a in r.atoms])
        from chimerax.core.objects import Objects
        from chimerax.std_commands.view import view
        view(session, Objects(atoms=atoms))
