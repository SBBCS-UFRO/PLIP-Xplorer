"""Standard-library tests: python -m unittest discover -s chimerax/test."""
import csv
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'plip_chimerax_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'chimerax' / 'src')]
sys.modules[PACKAGE] = package
from plip_chimerax_test.report import KINDS, read_report, write_csv
from plip_chimerax_test.backend import AnalysisError, engine_command, run_engine
from plip_chimerax_test.appearance import distance_labels, default_style
from plip_chimerax_test.report import Interaction


def xml_report(kind, coordinates, extra=''):
    points = ''.join(f'<{name}><z>{p[2]}</z><x>{p[0]}</x><y>{p[1]}</y></{name}>'
                     for name, p in coordinates.items())
    return f'''<report><plipversion>3.0.1</plipversion><bindingsite>
      <identifiers><hetid>LIG</hetid><chain></chain><position>-1</position></identifiers>
      <interactions><{kind}><contact id="1"><restype>ASP</restype><resnr>10</resnr>
      <reschain>A</reschain>{extra}{points}</contact></{kind}></interactions>
      </bindingsite></report>'''


class ReportTests(unittest.TestCase):
    def parse(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.xml'
            path.write_text(xml)
            return read_report(path)

    def test_existing_plip_fixture(self):
        report = read_report(ROOT / 'plip/test/xml/1vsn.report.xml')
        self.assertEqual(report.sites[0].identifier, 'NFT:A:283')
        self.assertEqual(len(report.sites[0].interactions), 13)
        self.assertEqual(report.sites[0].interactions[0].points[0], (-7.395, 24.225, 6.614))

    def test_all_eight_classes_preserve_points_and_measurements(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                points = {'ligcoo': (1, 2, 3), 'protcoo': (4, 5, 6)}
                if kind == 'water_bridges':
                    points['watercoo'] = (7, 8, 9)
                if kind == 'metal_complexes':
                    points = {'metalcoo': (1, 2, 3), 'targetcoo': (4, 5, 6)}
                report = self.parse(xml_report(kind, points, '<dist>3.14</dist><angle>42</angle>'))
                contact = report.sites[0].interactions[0]
                self.assertEqual(report.sites[0].identifier, 'LIG::-1')
                self.assertEqual(contact.fields['angle'], '42')
                self.assertEqual(contact.points[0], (1, 2, 3))
                if kind == 'water_bridges':
                    self.assertEqual(contact.segments, (((1, 2, 3), (7, 8, 9)), ((7, 8, 9), (4, 5, 6))))
                else:
                    self.assertEqual(contact.segments, (((1, 2, 3), (4, 5, 6)),))

    def test_invalid_coordinates_and_unknown_classes_fail_loudly(self):
        for xml in [xml_report('hydrogen_bonds', {'ligcoo': (1, 2, 3)}),
                    xml_report('hydrogen_bonds', {'ligcoo': ('nan', 2, 3), 'protcoo': (4, 5, 6)}),
                    xml_report('new_interactions', {}), '<html/>', '<report>']:
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                self.parse(xml)

    def test_csv_water_is_one_interaction_with_both_distances(self):
        report = self.parse(xml_report('water_bridges', {'ligcoo': (1, 2, 3),
            'watercoo': (2, 3, 4), 'protcoo': (4, 5, 6)}, '<dist_a-w>2.8</dist_a-w><dist_d-w>3.1</dist_d-w>'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.csv'
            write_csv(report, path)
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['distance_A'], '2.8 / 3.1')
            self.assertIn('watercoo', rows[0]['details_json'])


class AppearanceTests(unittest.TestCase):
    def test_water_labels_follow_the_donor_direction(self):
        for protisdon, expected in [('True', ('2.70 Å', '3.10 Å')),
                                   ('False', ('3.10 Å', '2.70 Å'))]:
            contact = Interaction('water_bridges', '1', (), (),
                {'protisdon': protisdon, 'dist_a-w': '2.70', 'dist_d-w': '3.10'})
            self.assertEqual(distance_labels(contact), expected)

    def test_hydrogen_label_uses_reported_heavy_atom_distance(self):
        contact = Interaction('hydrogen_bonds', '1', (), (), {'dist_d-a': '3.20', 'dist_h-a': '2.15'})
        self.assertEqual(distance_labels(contact), ('3.20 Å',))

    def test_presets_do_not_share_mutable_contact_styles(self):
        a, b = default_style(), default_style()
        a['contacts']['pi_stacks']['radius'] = 0.2
        self.assertEqual(b['contacts']['pi_stacks']['radius'], 0.08)


class BackendTests(unittest.TestCase):
    def test_virtualenv_python_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'python'
            try:
                path.symlink_to(sys.executable)
            except OSError:
                self.skipTest('Creating symlinks is unavailable on this system')
            args = engine_command(path, '/tmp/input.pdb', directory)
            self.assertEqual(args[0], str(path))

    def test_command_does_not_request_pymol_or_interpret_shell_text(self):
        args = engine_command(sys.executable, '/tmp/a ; $test.pdb', '/tmp/with spaces', no_hydro=True)
        self.assertIn(str(Path('/tmp/a ; $test.pdb').resolve()), args)
        self.assertIn('--nohydro', args)
        self.assertNotIn('-y', args)
        self.assertNotIn('-p', args)

    def test_failed_process_does_not_return_a_stale_report(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'report.xml').write_text('old report')
            with self.assertRaisesRegex(AnalysisError, 'already contains'):
                run_engine(sys.executable, '/tmp/input.pdb', directory)

    def test_process_failure_surfaces_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(PACKAGE + '.backend.engine_command', return_value=[sys.executable, '-c',
                       'import sys; print("missing Open Babel"); sys.exit(2)']):
                with self.assertRaisesRegex(AnalysisError, 'missing Open Babel'):
                    run_engine(sys.executable, '/tmp/input.pdb', directory)

    def test_cancellation_and_timeout_stop_process(self):
        for kwargs in ({'cancelled': lambda: True}, {'timeout': 0.01}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as directory:
                with patch(PACKAGE + '.backend.engine_command', return_value=[sys.executable,
                           '-c', 'import time; time.sleep(30)']):
                    with self.assertRaises(AnalysisError):
                        run_engine(sys.executable, '/tmp/input.pdb', directory, **kwargs)


if __name__ == '__main__':
    unittest.main()
