"""Read PLIP's public XML format without importing PLIP, lxml or Open Babel."""
from dataclasses import dataclass
import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


# Key, human-readable name, RGBA. Order matches PLIP's report writer.
KINDS = {
    'hydrophobic_interactions': ('Hydrophobic contacts', (160, 160, 160, 255)),
    'hydrogen_bonds': ('Hydrogen bonds', (60, 130, 255, 255)),
    'water_bridges': ('Water bridges', (0, 190, 220, 255)),
    'salt_bridges': ('Salt bridges', (235, 190, 30, 255)),
    'pi_stacks': ('Pi stacking', (70, 185, 85, 255)),
    'pi_cation_interactions': ('Pi–cation interactions', (240, 135, 35, 255)),
    'halogen_bonds': ('Halogen bonds', (180, 90, 225, 255)),
    'metal_complexes': ('Metal coordination', (230, 80, 160, 255)),
}


@dataclass(frozen=True)
class Interaction:
    kind: str
    identifier: str
    residue: tuple
    points: tuple
    fields: dict

    @property
    def segments(self):
        return tuple(zip(self.points, self.points[1:]))

    @property
    def distance_text(self):
        if self.kind == 'water_bridges':
            return ' / '.join(self.fields.get(k, '') for k in ('dist_a-w', 'dist_d-w'))
        return next((self.fields[k] for k in ('dist', 'dist_d-a', 'centdist')
                     if k in self.fields), '')


@dataclass(frozen=True)
class Site:
    identifier: str
    members: tuple
    interactions: tuple


@dataclass(frozen=True)
class Report:
    path: Path
    version: str
    sites: tuple


def _coordinate(node, name):
    try:
        point = tuple(float(node.findtext(f'{name}/{axis}', '')) for axis in 'xyz')
    except ValueError as err:
        raise ValueError(f'Missing or invalid {name} in {node.tag} #{node.get("id")}') from err
    if not all(math.isfinite(x) for x in point):
        raise ValueError(f'Non-finite coordinate in {node.tag}')
    return point


def read_report(path):
    path = Path(path)
    # Refuse declarations/entities; PLIP reports do not use either.
    raw = path.read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('XML declarations with external entities are not PLIP reports')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as err:
        raise ValueError(f'Invalid PLIP XML: {err}') from err
    if root.tag != 'report' or root.find('plipversion') is None:
        raise ValueError('Expected a PLIP XML report with a plipversion element')
    sites = []
    identifiers = set()
    for element in root.findall('bindingsite'):
        parts = tuple(element.findtext(f'identifiers/{key}', '').strip()
                      for key in ('hetid', 'chain', 'position'))
        if not parts[0] or not parts[2]:
            raise ValueError('Binding site is missing its ligand identifier')
        identifier = ':'.join(parts)
        if identifier in identifiers:
            raise ValueError(f'Duplicate binding site: {identifier}')
        identifiers.add(identifier)
        members = tuple(n.text for n in element.findall('identifiers/members/member')) or (identifier,)
        interactions = []
        for group in element.findall('interactions/*'):
            if group.tag not in KINDS:
                if len(group):
                    raise ValueError(f'Unsupported PLIP interaction class: {group.tag}')
                continue
            for node in group:
                fields = {child.tag: (tuple(c.text or '' for c in child) if len(child)
                                      else child.text or '') for child in node}
                coordinate_names = ('metalcoo', 'targetcoo') if group.tag == 'metal_complexes' else (
                    ('ligcoo', 'watercoo', 'protcoo') if group.tag == 'water_bridges'
                    else ('ligcoo', 'protcoo'))
                interactions.append(Interaction(
                    group.tag, node.get('id', ''),
                    tuple(node.findtext(key, '') for key in ('restype', 'reschain', 'resnr')),
                    tuple(_coordinate(node, name) for name in coordinate_names), fields))
        sites.append(Site(identifier, members, tuple(interactions)))
    return Report(path.resolve(), root.findtext('plipversion', ''), tuple(sites))


def write_csv(report, path):
    """One row per scientific interaction, with both water distances and full XML fields."""
    with open(path, 'w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['site', 'type', 'id', 'residue', 'chain', 'number',
                         'distance_A', 'PLIP_version', 'details_json'])
        for site in report.sites:
            for contact in site.interactions:
                writer.writerow([site.identifier, contact.kind, contact.identifier,
                                 *contact.residue, contact.distance_text, report.version,
                                 json.dumps(contact.fields, ensure_ascii=False)])
