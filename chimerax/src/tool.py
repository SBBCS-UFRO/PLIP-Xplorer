"""Dockable Qt interface using ChimeraX's Qt compatibility layer."""
from pathlib import Path

from chimerax.core.tools import ToolInstance
from chimerax.ui import MainToolWindow
from Qt.QtCore import Qt
from Qt.QtGui import QColor, QPixmap
from Qt.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout,
                          QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
                          QTableWidgetItem, QVBoxLayout, QAbstractItemView, QWidget, QTabWidget)

from .report import KINDS, write_csv
from .settings import get_settings
from .i18n import Language, LANGUAGES, TITLE, COPYRIGHT


class PLIPTool(ToolInstance):
    SESSION_SAVE = False  # Native drawings survive .cxs; reload XML to reopen the table.
    help = 'help:user/tools/plip-xplorer.html'

    def __init__(self, session, tool_name='PLIP-Xplorer'):
        super().__init__(session, tool_name)
        self.display_name = TITLE
        self.language = Language(get_settings(session).language)
        self.tr = self.language.tr
        self._closed = False
        self.job = None
        self.result = None
        self.tool_window = MainToolWindow(self)
        outer = QVBoxLayout(self.tool_window.ui_area)
        header = QHBoxLayout()
        self.logo = QLabel()
        pixel_ratio = self.tool_window.ui_area.devicePixelRatioF()
        pixmap = QPixmap(str(Path(__file__).parent / 'assets/plip-xplorer.png')).scaled(
            round(76 * pixel_ratio), round(78 * pixel_ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap.setDevicePixelRatio(pixel_ratio)
        self.logo.setPixmap(pixmap)
        header.addWidget(self.logo)
        intro = QLabel(TITLE)
        intro.setStyleSheet('font-size: 17px; font-weight: 600;')
        header.addWidget(intro, 1)
        outer.addLayout(header)
        languages = QHBoxLayout()
        languages.addWidget(QLabel('Language'))
        self.language_menu = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_menu.addItem(name, code)
        self.language_menu.setCurrentIndex(self.language_menu.findData(self.language.code))
        languages.addWidget(self.language_menu, 1)
        outer.addLayout(languages)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        analysis_widget = QWidget()
        self.tabs.addTab(analysis_widget, 'Analysis')
        layout = QVBoxLayout(analysis_widget)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        from chimerax.atomic.widgets import AtomicStructureMenuButton
        self.model_menu = AtomicStructureMenuButton(session)
        form.addRow('Structure', self.model_menu)
        self.python = QLineEdit(get_settings(session).python)
        self.python.setPlaceholderText('Python executable in the PLIP environment')
        row = QHBoxLayout()
        row.addWidget(self.python)
        browse = QPushButton('Browse…')
        browse.clicked.connect(self._browse_python)
        row.addWidget(browse)
        form.addRow('PLIP Python', row)
        self.output = QLineEdit(str(Path.home() / 'PLIP-results'))
        row = QHBoxLayout()
        row.addWidget(self.output)
        browse_output = QPushButton('Browse…')
        browse_output.clicked.connect(self._browse_output)
        row.addWidget(browse_output)
        form.addRow('Results folder', row)
        layout.addLayout(form)
        self.no_hydro = QCheckBox('Keep existing hydrogens (PLIP --nohydro)')
        self.no_hydro.setToolTip('Use only with a structure whose hydrogens have already been prepared.')
        layout.addWidget(self.no_hydro)
        row = QHBoxLayout()
        self.analyze = QPushButton('Analyze structure')
        self.analyze.clicked.connect(self._analyze)
        self.cancel = QPushButton('Cancel')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self._cancel)
        self.load = QPushButton('Load PLIP XML…')
        self.load.clicked.connect(self._load)
        for widget in (self.analyze, self.cancel, self.load):
            row.addWidget(widget)
        layout.addLayout(row)
        self.status = QLabel('Ready. Analysis creates a separate snapshot of the active coordinates.')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.sites = QComboBox()
        self.sites.currentIndexChanged.connect(self._refresh)
        layout.addWidget(self.sites)
        self.filters = {}
        grid = QGridLayout()
        for i, (kind, (label, color)) in enumerate(KINDS.items()):
            check = QCheckBox(label)
            check.setChecked(True)
            check.stateChanged.connect(self._refresh)
            check.setStyleSheet(f'QCheckBox {{ color: rgb{color[:3]}; }}')
            self.filters[kind] = check
            grid.addWidget(check, i // 2, i % 2)
        layout.addLayout(grid)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Interaction', 'Receptor residue', 'Distance (Å)'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellClicked.connect(self._select_contact)
        self.table.setToolTip('Click a row to select its receptor residue. Hover for all PLIP measurements. '
                              'Water distances are acceptor–water / donor–water.')
        self.table.setMinimumHeight(180)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.focus = QPushButton('Focus binding site')
        self.focus.clicked.connect(self._focus)
        self.export = QPushButton('Export CSV…')
        self.export.clicked.connect(self._export)
        self.save = QPushButton('Save ChimeraX session…')
        self.save.clicked.connect(self._save)
        for button in (self.focus, self.export, self.save):
            button.setEnabled(False)
            row.addWidget(button)
        layout.addLayout(row)
        from .appearance_ui import AppearancePanel
        self.appearance = AppearancePanel(self, self.tabs)
        self.credit = QLabel(COPYRIGHT)
        self.credit.setWordWrap(True)
        self.credit.setStyleSheet('font-size: 10px;')
        outer.addWidget(self.credit)
        self.language.capture(self.tool_window.ui_area)
        self.language.change(self.language.code)
        self.language_menu.currentIndexChanged.connect(self._change_language)
        self.tool_window.manage(placement='side')

    def _change_language(self, *args):
        code = self.language_menu.currentData()
        self.language.change(code)
        get_settings(self.session).language = code
        # Retranslate result text without rebuilding labels, changing the camera,
        # or disturbing the active analysis and selected binding site.
        if self.result:
            blocked = self.sites.blockSignals(True)
            for i, site in enumerate(self.result[0].sites):
                self.sites.setItemText(i, self._site_text(site))
            self.sites.blockSignals(blocked)
        for row, contact in enumerate(getattr(self, '_rows', [])):
            self.table.item(row, 0).setText(self.tr(KINDS[contact.kind][0]))
        self.table.resizeColumnsToContents()

    def _site_text(self, site):
        return self.tr('{identifier} · {count} interactions',
                       identifier=site.identifier, count=len(site.interactions))

    def _browse_python(self):
        path, _ = QFileDialog.getOpenFileName(self.tool_window.ui_area, self.tr('Choose PLIP Python'))
        if path:
            self.python.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self.tool_window.ui_area, self.tr('Results folder'))
        if path:
            self.output.setText(path)

    def _busy(self, busy):
        self.analyze.setEnabled(not busy)
        self.load.setEnabled(not busy)
        self.cancel.setEnabled(busy)

    def _analyze(self):
        structure = self.model_menu.value
        if structure is None:
            self.language.message(self.status, 'Open and choose an atomic structure first.')
            return
        from .commands import prepare_analysis, plip_settings
        from .job import AnalysisJob
        try:
            python, directory, position = prepare_analysis(
                self.session, structure, self.python.text().strip(), self.output.text().strip() or None)
            plip_settings(self.session, python)
            self.job = AnalysisJob(self.session, python, directory, position,
                                   self.no_hydro.isChecked(), self._finished, source=structure)
            self._busy(True)
            self.language.message(self.status, 'Analyzing with PLIP… Results: {directory}', directory=directory)
            self.job.start()
        except Exception as err:
            self._finished(None, str(err))

    def _cancel(self):
        if self.job:
            self.job.cancel()
            self.cancel.setEnabled(False)
            self.language.message(self.status, 'Cancelling PLIP…')

    def _finished(self, result, error):
        if self._closed:
            return
        self.job = None
        self._busy(False)
        if error:
            self.status.setText(error)
            return
        self.result = result
        report = result[0]
        self.sites.blockSignals(True)
        self.sites.clear()
        for site in report.sites:
            self.sites.addItem(self._site_text(site))
        self.sites.blockSignals(False)
        self.status.setText(f'PLIP {report.version} · {report.path}')
        self.focus.setEnabled(bool(report.sites))
        self.export.setEnabled(True)
        self.save.setEnabled(True)
        self._refresh()
        if get_settings(self.session).appearance:
            self.appearance.apply()

    def _load(self):
        model = self.model_menu.value
        if model is None:
            self.language.message(self.status, 'Choose the atomic model used to generate the PLIP report.')
            return
        path, _ = QFileDialog.getOpenFileName(self.tool_window.ui_area, self.tr('Load PLIP XML'), '', 'XML (*.xml)')
        if path:
            from .commands import plip_load
            try:
                self._finished(plip_load(self.session, path, model), None)
            except Exception as err:
                self.status.setText(str(err))

    def _refresh(self, *args):
        self._rows = []
        self.table.setRowCount(0)
        if not self.result or self.sites.currentIndex() < 0:
            return
        report, model, root, groups = self.result
        if model.deleted or root.deleted:
            self.language.message(self.status, 'The result model was closed. Load the report or analyze again.')
            return
        site = report.sites[self.sites.currentIndex()]
        for (site_id, kind), group in groups.items():
            if not group.deleted:
                group.display = site_id == site.identifier and self.filters[kind].isChecked()
        for contact in site.interactions:
            if not self.filters[contact.kind].isChecked():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._rows.append(contact)
            residue = f'{contact.residue[0]} {contact.residue[1]}:{contact.residue[2]}'
            values = [self.tr(KINDS[contact.kind][0]), residue, contact.distance_text]
            tooltip = '\n'.join(f'{key}: {value}' for key, value in contact.fields.items())
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                if col == 0:
                    item.setForeground(QColor(*KINDS[contact.kind][1]))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        if hasattr(self, 'appearance'):
            try:
                self.appearance.apply_result()
                colors = self.appearance.style()['contacts']
                for row, contact in enumerate(self._rows):
                    self.table.item(row, 0).setForeground(QColor(colors[contact.kind]['color']))
                for kind, check in self.filters.items():
                    check.setStyleSheet('QCheckBox { color: ' + colors[kind]['color'] + '; }')
            except Exception as err:
                self.language.message(self.status, 'Appearance: {error}', error=str(err))

    def _select_contact(self, row, column):
        if not self.result or self.result[1].deleted or row >= len(self._rows):
            return
        contact = self._rows[row]
        self.session.selection.clear()
        for residue in self.result[1].residues:
            if (residue.name, residue.chain_id.strip(), str(residue.number)) == contact.residue:
                residue.atoms.selecteds = True

    def _focus(self):
        if not self.result or self.result[1].deleted or self.sites.currentIndex() < 0:
            return
        from .visualize import style_site
        style_site(self.session, self.result[1], self.result[0].sites[self.sites.currentIndex()])
        self.appearance.apply_result()

    def _export(self):
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self.tool_window.ui_area, self.tr('Export interactions'),
                                              'plip-interactions.csv', 'CSV (*.csv)')
        if path:
            try:
                write_csv(self.result[0], path)
            except OSError as err:
                self.status.setText(str(err))

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self.tool_window.ui_area, self.tr('Save ChimeraX session'),
                                              'plip-session.cxs', 'ChimeraX session (*.cxs)')
        if path:
            from chimerax.core.commands import run, StringArg
            run(self.session, 'save ' + StringArg.unparse(path) + ' format session')

    def delete(self):
        self._closed = True
        self.appearance.close()
        if self.job:
            self.job.callback = None
            self.job.cancel()
        super().delete()
