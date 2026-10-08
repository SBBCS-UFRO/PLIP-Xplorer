"""Presentation only: these options never change PLIP's scientific report."""
from .report import KINDS


def default_style():
    return dict(background='#ffffff', lighting='simple', material='default',
                silhouettes=False, silhouette_width=1.0, depth_cue=False, camera='perspective',
                cartoon=True, cartoon_color='#8c9baf', cartoon_transparency=75,
                ligand_color='#f5a02d', receptor_color='#73a5d7', element_colors=True,
                ligand_style='sticks', receptor_style='sticks', bond_radius=0.18,
                hydrogens=False, waters=True, markers=True,
                residue_labels=False, ligand_labels=False, distances=False,
                label_format='Name chain:number', label_color='auto', label_background=False,
                label_height=0.55, distance_height=0.4, font='Arial', on_top=True,
                label_offset_x=0.2, label_offset_y=0.2, label_offset_z=0.5,
                distance_offset_x=0.0, distance_offset_y=0.0, distance_offset_z=0.5,
                contacts={k: dict(color='#%02x%02x%02x' % c[:3], radius=0.055 if k ==
                    'hydrophobic_interactions' else 0.08, dashes=6) for k, (_, c) in KINDS.items()})


def preset_style(name):
    style = default_style()
    if name == 'Publication':
        style.update(lighting='soft', cartoon=False, residue_labels=True, distances=True)
    elif name == 'Dark presentation':
        style.update(background='#10151e', lighting='full', material='shiny',
                     residue_labels=True, distances=True, label_height=0.7, distance_height=0.5)
    elif name == 'Illustration':
        style.update(lighting='flat', silhouettes=True, cartoon_transparency=85, residue_labels=True)
    return style


def distance_labels(contact):
    """Reported values in drawing order, including donor direction of water bridges."""
    if contact.kind == 'water_bridges':
        keys = ('dist_a-w', 'dist_d-w') if contact.fields.get('protisdon') == 'True' else (
            'dist_d-w', 'dist_a-w')
    else:
        keys = ('dist_d-a',) if contact.kind == 'hydrogen_bonds' else (
            ('centdist',) if contact.kind == 'pi_stacks' else ('dist',))
    return tuple(f'{contact.fields[key]} Å' if contact.fields.get(key) else '' for key in keys)


def rgba(hex_color):
    return tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5)) + (255,)


def apply_scene(session, style):
    from chimerax.core.commands import run
    from chimerax.std_commands.lighting import lighting
    from chimerax.std_commands.material import material
    from chimerax.std_commands.graphics import graphics_silhouettes
    session.main_view.background_color = tuple(v / 255 for v in rgba(style['background']))
    lighting(session, preset=style['lighting'], depth_cue=style['depth_cue'])
    material(session, preset=style['material'])
    graphics_silhouettes(session, enable=style['silhouettes'], width=style['silhouette_width'])
    camera = 'mono' if style['camera'] == 'perspective' else 'ortho'
    expected_name = 'mono' if camera == 'mono' else 'orthographic'
    if session.main_view.camera.name != expected_name:
        run(session, 'camera ' + camera)


class Presentation:
    """Own only our annotation model and labels on PLIP's own pseudobonds."""
    def __init__(self, session):
        self.session = session
        self.annotation_model = None

    def apply(self, result, site, enabled, style):
        from chimerax.atomic import Atoms, Pseudobonds
        from chimerax.atomic.colors import element_colors
        from chimerax.core.objects import Objects
        from chimerax.label.label3d import label, label_delete
        from chimerax.markers import MarkerSet
        from .visualize import style_site, site_residues
        report, model, root, groups = result
        if model.deleted or root.deleted:
            return
        style_site(self.session, model, site, focus=False)
        model.residues.ribbon_displays = style['cartoon']
        color = rgba(style['cartoon_color'])[:3] + (round(255 * (1 - style['cartoon_transparency']/100)),)
        model.residues.ribbon_colors = color
        ligand = set(site_residues(model, site, include_contacts=False))
        residues = site_residues(model, site)
        modes = dict(sticks=model.atoms[0].STICK_STYLE, balls=model.atoms[0].BALL_STYLE,
                     spheres=model.atoms[0].SPHERE_STYLE)
        model.bonds.radii = style['bond_radius']
        for residue in residues:
            role = 'ligand' if residue in ligand else 'receptor'
            residue.atoms.draw_modes = modes[style[role + '_style']]
            residue.atoms.colors = rgba(style[role + '_color'])
            if style['element_colors']:
                hetero = residue.atoms.filter(residue.atoms.element_numbers != 6)
                hetero.colors = element_colors(hetero.element_numbers)
        if not style['hydrogens']:
            model.atoms.filter(model.atoms.element_numbers == 1).displays = False
        if not style['waters']:
            for residue in model.residues:
                if residue.name in ('HOH', 'WAT', 'DOD'):
                    residue.atoms.displays = False

        label_options = dict(color=style['label_color'] if style['label_color'] == 'auto' else
                             rgba(style['label_color']), font=style['font'], on_top=style['on_top'],
                             bg_color=rgba(style['background']) if style['label_background'] else 'none')
        visible_contacts = []
        for (site_id, kind), group in groups.items():
            if group.deleted:
                continue
            group.display = site_id == site.identifier and enabled[kind]
            pbgroup = group.pseudobond_group('contacts')
            config = style['contacts'][kind]
            pbgroup.dashes = config['dashes']
            pbgroup.pseudobonds.colors = rgba(config['color'])
            pbgroup.pseudobonds.radii = config['radius']
            group.atoms.colors = rgba(config['color'])
            # ChimeraX requires positive radii; subpixel anchors keep bonds/labels visible.
            group.atoms.radii = 0.08 if style['markers'] else 0.0001
            label_delete(self.session, Objects(pseudobonds=pbgroup.pseudobonds), 'pseudobonds')
            if not group.display:
                continue
            contacts = [c for c in site.interactions if c.kind == kind]
            visible_contacts.extend(contacts)
            if style['distances']:
                texts = [text for contact in contacts for text in distance_labels(contact)]
                for bond, text in zip(pbgroup.pseudobonds, texts):
                    if text:
                        label(self.session, Objects(pseudobonds=Pseudobonds([bond])), 'pseudobonds',
                              text=text, height=style['distance_height'],
                              offset=tuple(style[f'distance_offset_{a}'] for a in 'xyz'), **label_options)

        if self.annotation_model is not None and not self.annotation_model.deleted:
            self.annotation_model.delete()
        self.annotation_model = None
        if not (style['residue_labels'] or style['ligand_labels']):
            return
        anchors = MarkerSet(self.session, 'PLIP-Xplorer residue labels')
        root.add([anchors])
        self.annotation_model = anchors
        visible_residues = {c.residue for c in visible_contacts}
        for residue in residues:
            key = (residue.name, residue.chain_id.strip(), str(residue.number))
            show = style['ligand_labels'] if residue in ligand else (
                style['residue_labels'] and key in visible_residues)
            if not show:
                continue
            atom = residue.find_atom('CA') or residue.atoms[0]
            anchor = anchors.create_marker(atom.coord, (255, 255, 255, 255), 0.0001)
            number = str(residue.number) + residue.insertion_code.strip()
            text = f'{residue.name} {residue.chain_id.strip()}:{number}'
            if style['label_format'] == 'Name number':
                text = f'{residue.name} {number}'
            elif style['label_format'] == 'Chain:number':
                text = f'{residue.chain_id.strip()}:{number}'
            label(self.session, Objects(atoms=Atoms([anchor])), 'atoms', text=text,
                  height=style['label_height'], offset=tuple(style[f'label_offset_{a}'] for a in 'xyz'),
                  **label_options)


def export_image(session, result, path, *, width, height, supersample=3,
                 transparent=False, quality=95, only_result=True):
    """Export the native renderer and restore temporarily isolated scene visibility."""
    from pathlib import Path
    from chimerax.image_formats.save import save_image
    if result is None or result[1].deleted or result[2].deleted:
        raise ValueError('Load or analyze a PLIP result before exporting an image.')
    suffix = Path(path).suffix.lower()
    if suffix not in ('.png', '.tif', '.tiff', '.jpg', '.jpeg'):
        raise ValueError('Choose PNG, TIFF or JPEG for the image.')
    if transparent and suffix in ('.jpg', '.jpeg'):
        raise ValueError('JPEG cannot have a transparent background. Choose PNG or TIFF.')
    if width <= 0 or height <= 0 or supersample < 1:
        raise ValueError('Image dimensions and supersampling must be positive.')
    if width * height * supersample ** 2 > 100_000_000:
        raise ValueError('This combination renders over 100 megapixels. Lower the size or supersampling.')
    displays = {}
    try:
        if only_result:
            keep = result[1]
            # Preserve ancestors when a report was loaded onto a submodel.
            ancestors = set()
            node = keep
            while node is not None:
                ancestors.add(node)
                node = node.parent
            for model in session.models.list():
                if model in ancestors or model.parent in ancestors and model is not keep:
                    displays[model] = model.display
                    model.display = model in ancestors
                elif model.parent is None:
                    displays[model] = model.display
                    model.display = False
            # The analyzed structure's children include the PLIP drawings and labels.
            for child in keep.child_models():
                if child in displays:
                    child.display = displays.pop(child)
        session.update_loop.update_graphics_now()
        save_image(session, str(path), width=width, height=height, supersample=supersample,
                   transparent_background=transparent, quality=quality)
        if not Path(path).is_file():
            raise RuntimeError('The renderer did not create the image.')
    finally:
        for model, display in displays.items():
            if not model.deleted:
                model.display = display
