"""Plugin-scoped translations; canonical style values never depend on language."""
import json
from pathlib import Path

LANGUAGES = {'en': 'English', 'es': 'Español', 'de': 'Deutsch', 'fr': 'Français',
             'zh': '中文（简体）', 'ja': '日本語', 'pt': 'Português'}
TITLE = 'PLIP-Xplorer 1.0.0'
COPYRIGHT = '© 2026 Structural Bioinformatics & Bioactive Compound Synthesis Lab - UFRO'
_CATALOGS = {}


def catalog(language):
    language = language if language in LANGUAGES else 'en'
    if language not in _CATALOGS:
        _CATALOGS[language] = json.loads(
            (Path(__file__).parent / 'locales' / (language + '.json')).read_text(encoding='utf-8'))
    return _CATALOGS[language]


def translate(source, language='en', **values):
    return catalog(language).get(source, source).format(**values)


class Language:
    """Capture only plugin-owned text; never install an application-wide translator."""
    def __init__(self, code):
        self.code = code if code in LANGUAGES else 'en'
        self.bindings = []
        self.messages = {}

    def tr(self, source, **values):
        return translate(source, self.code, **values)

    def message(self, label, source, **values):
        self.messages[label] = (source, values)
        label.setText(self.tr(source, **values))

    def capture(self, root):
        from Qt.QtCore import QObject
        from Qt.QtWidgets import QLabel, QAbstractButton, QGroupBox, QLineEdit, QComboBox, QTabWidget, QTableWidget
        known = catalog('en')
        def bind(getter, setter):
            source = getter()
            if source in known:
                self.bindings.append((getter, setter, source))
        for widget in [root] + root.findChildren(QObject):
            if isinstance(widget, (QLabel, QAbstractButton)):
                bind(widget.text, widget.setText)
            if isinstance(widget, QGroupBox):
                bind(widget.title, widget.setTitle)
            if isinstance(widget, QLineEdit):
                bind(widget.placeholderText, widget.setPlaceholderText)
            if hasattr(widget, 'toolTip'):
                bind(widget.toolTip, widget.setToolTip)
            if isinstance(widget, QComboBox) and widget.property('plipCanonical'):
                for i in range(widget.count()):
                    bind(lambda w=widget, n=i: w.itemText(n),
                         lambda text, w=widget, n=i: self._combo_text(w, n, text))
            if isinstance(widget, QTabWidget):
                for i in range(widget.count()):
                    bind(lambda w=widget, n=i: w.tabText(n),
                         lambda text, w=widget, n=i: w.setTabText(n, text))
            if isinstance(widget, QTableWidget):
                for i in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(i)
                    if item:
                        bind(item.text, item.setText)
            if hasattr(widget, 'translate_color_dialog'):
                widget.translate_color_dialog = self.tr

    @staticmethod
    def _combo_text(widget, index, text):
        blocked = widget.blockSignals(True)
        try:
            widget.setItemText(index, text)
        finally:
            widget.blockSignals(blocked)

    def change(self, code):
        previous = self.code
        self.code = code if code in LANGUAGES else 'en'
        for getter, setter, source in self.bindings:
            # A dynamic status may have replaced its original static text.
            if getter() in (source, translate(source, previous)):
                setter(self.tr(source))
        for label, (source, values) in self.messages.items():
            if label.text() == translate(source, previous, **values):
                label.setText(self.tr(source, **values))


def canonical_items(combo, items):
    combo.setProperty('plipCanonical', True)
    for value in items:
        combo.addItem(value, value)
