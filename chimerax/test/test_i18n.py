"""Catalog integrity and placeholder checks without importing Qt or ChimeraX."""
import importlib.util
from pathlib import Path
from string import Formatter
import unittest

path = Path(__file__).resolve().parents[1] / 'src/i18n.py'
spec = importlib.util.spec_from_file_location('plip_i18n', path)
i18n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i18n)


class TranslationTests(unittest.TestCase):
    def test_every_language_covers_the_catalog_and_preserves_placeholders(self):
        reference = i18n.catalog('en')
        fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name}
        for code in i18n.LANGUAGES:
            with self.subTest(language=code):
                translated = i18n.catalog(code)
                self.assertEqual(set(translated), set(reference))
                for source, value in translated.items():
                    self.assertTrue(value.strip(), source)
                    self.assertEqual(fields(source), fields(value), (code, source))
                    values = {key: '42' for key in fields(source)}
                    self.assertTrue(i18n.translate(source, code, **values))

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(i18n.translate('Analyze structure', 'missing'), 'Analyze structure')

    def test_paths_are_not_interpreted_as_translation_templates(self):
        value = '/tmp/{protein}/中文.xml'
        self.assertIn(value, i18n.translate('Image saved: {path}', 'ja', path=value))


if __name__ == '__main__':
    unittest.main()
