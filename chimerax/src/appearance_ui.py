"""Appearance and image-export tabs; all rendering remains native to ChimeraX."""
import json
from pathlib import Path
from Qt.QtCore import QTimer
from Qt.QtGui import QColor
from Qt.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QScrollArea, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QColorDialog, QFileDialog, QLabel)
from .appearance import default_style, preset_style, apply_scene, Presentation, export_image
from .report import KINDS
from .settings import get_settings
from .i18n import canonical_items


class ColorButton(QPushButton):
    def __init__(self, value, changed):
        super().__init__()
        self.changed = changed
        self.translate_color_dialog = lambda text: text
        self.set_value(value)
        self.clicked.connect(self.choose)

    def set_value(self, value):
        color = QColor(value)
        if not color.isValid():
            raise ValueError(f'Invalid color: {value}')
        self.value = color.name()
        self.setText(self.value)
        fg = '#000000' if color.lightness() > 140 else '#ffffff'
        self.setStyleSheet(f'background-color: {self.value}; color: {fg};')

    def choose(self):
        color = QColorDialog.getColor(QColor(self.value), self, self.translate_color_dialog('Choose color'))
        if color.isValid():
            self.set_value(color.name())
            self.changed()


class AppearancePanel:
    def __init__(self, tool, tabs):
        self.tool = tool
        self.tr = tool.tr
        self.controls = {}
        self.contact_controls = {}
        self.presentation = Presentation(tool.session)
        self.loading = True
        self._owns_mouse_mode = False
        self._previous_mouse_mode = None
        self.timer = QTimer(tool.tool_window.ui_area)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.apply)
        self.widget = QWidget()
        body = QVBoxLayout(self.widget)
        presets = QHBoxLayout()
        self.preset = QComboBox()
        canonical_items(self.preset, ['Original', 'Publication', 'Dark presentation', 'Illustration'])
        presets.addWidget(self.preset)
        button = QPushButton('Apply preset')
        button.clicked.connect(lambda: self.set_style(preset_style(self.preset.currentData())))
        presets.addWidget(button)
        body.addLayout(presets)
        note = QLabel('Preview updates automatically. Background, lighting and camera affect the whole scene.')
        note.setWordWrap(True)
        body.addWidget(note)
        self.feedback = QLabel('')
        self.feedback.setWordWrap(True)
        body.addWidget(self.feedback)
        self._form(body, 'Scene', [
            ('background', 'Background', 'color'),
            ('lighting', 'Lighting', ['simple', 'soft', 'full', 'gentle', 'flat']),
            ('material', 'Material', ['default', 'shiny', 'dull', 'chimera']),
            ('camera', 'Camera', ['perspective', 'ortho']),
            ('silhouettes', 'Outline edges', bool),
            ('silhouette_width', 'Outline width (pixels)', (0.5, 5, 0.5)),
            ('depth_cue', 'Depth fog', bool)])
        self._form(body, 'Molecule', [
            ('cartoon', 'Show protein cartoon', bool),
            ('cartoon_color', 'Cartoon color', 'color'),
            ('cartoon_transparency', 'Cartoon transparency (%)', (0, 100, 1)),
            ('ligand_color', 'Ligand color', 'color'),
            ('receptor_color', 'Receptor color', 'color'),
            ('element_colors', 'Keep N/O/S/halogen element colors', bool),
            ('ligand_style', 'Ligand representation', ['sticks', 'balls', 'spheres']),
            ('receptor_style', 'Receptor representation', ['sticks', 'balls', 'spheres']),
            ('bond_radius', 'Bond radius (Å)', (0.05, 0.5, 0.01)),
            ('hydrogens', 'Show available hydrogens', bool),
            ('waters', 'Show bridging water atoms', bool),
            ('markers', 'Show interaction endpoint dots', bool)])
        self._form(body, '3D labels', [
            ('residue_labels', 'Label visible interacting residues', bool),
            ('ligand_labels', 'Label ligand', bool),
            ('distances', 'Show PLIP distances (Å)', bool),
            ('label_format', 'Residue text', ['Name chain:number', 'Name number', 'Chain:number']),
            ('font', 'Font', ['Arial', 'Helvetica', 'Times New Roman', 'Courier New']),
            ('label_height', 'Residue text height (Å)', (0.15, 2.0, 0.05)),
            ('distance_height', 'Distance text height (Å)', (0.15, 2.0, 0.05)),
            ('on_top', 'Keep labels in front', bool),
            ('label_background', 'Label background boxes', bool),
            ('label_offset_x', 'Residue label offset X (Å)', (-5.0, 5.0, 0.1)),
            ('label_offset_y', 'Residue label offset Y (Å)', (-5.0, 5.0, 0.1)),
            ('label_offset_z', 'Residue label offset Z (Å)', (-5.0, 5.0, 0.1)),
            ('distance_offset_x', 'Distance label offset X (Å)', (-5.0, 5.0, 0.1)),
            ('distance_offset_y', 'Distance label offset Y (Å)', (-5.0, 5.0, 0.1)),
            ('distance_offset_z', 'Distance label offset Z (Å)', (-5.0, 5.0, 0.1))])
        self.move_labels = QCheckBox('Move individual labels with right-button drag')
        self.move_labels.setToolTip('Arrange labels after choosing your style and filters. '
                                   'Style/filter changes rebuild labels; export and .cxs preserve manual placement.')
        self.move_labels.toggled.connect(self._move_labels)
        body.addWidget(self.move_labels)
        label_row = QHBoxLayout()
        self.auto_label_color = QCheckBox('Automatic label contrast')
        self.auto_label_color.setChecked(True)
        self.auto_label_color.toggled.connect(self.queue)
        self.label_color = ColorButton('#202020', self.queue)
        label_row.addWidget(self.auto_label_color)
        label_row.addWidget(self.label_color)
        body.addLayout(label_row)
        group = QGroupBox('Interaction colors and lines · dashes = 0 for solid lines')
        form = QFormLayout(group)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for kind, (name, _) in KINDS.items():
            defaults = default_style()['contacts'][kind]
            color = ColorButton(defaults['color'], self.queue)
            radius = self._spin((0.02, 0.4, 0.01))
            radius.setToolTip('Line radius in Å')
            dashes = self._spin((0, 20, 1))
            dashes.setToolTip('Number of dashes; 0 = solid')
            row = QHBoxLayout()
            for control in (color, radius, dashes):
                row.addWidget(control)
            form.addRow(name, row)
            self.contact_controls[kind] = (color, radius, dashes)
        body.addWidget(group)
        buttons = QHBoxLayout()
        for name, callback in [('Save as default', self.save_default), ('Save style…', self.save_style),
                               ('Load style…', self.load_style)]:
            button = QPushButton(name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        body.addLayout(buttons)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.widget)
        tabs.addTab(scroll, 'Appearance')
        self._build_export(tabs)
        self.set_style(default_style(), apply=False)
        saved = get_settings(tool.session).appearance
        if saved:
            try:
                self.set_style(json.loads(saved), apply=False)
            except (ValueError, TypeError, KeyError):
                self.set_style(default_style(), apply=False)
        self.loading = False

    def _spin(self, limits):
        integer = all(isinstance(x, int) for x in limits)
        widget = QSpinBox() if integer else QDoubleSpinBox()
        widget.setRange(*limits[:2])
        widget.setSingleStep(limits[2])
        widget.setKeyboardTracking(False)
        widget.valueChanged.connect(self.queue)
        return widget

    def _form(self, layout, title, specs):
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for key, text, kind in specs:
            if kind is bool:
                widget = QCheckBox()
                widget.toggled.connect(self.queue)
            elif kind == 'color':
                widget = ColorButton('#ffffff', self.queue)
            elif isinstance(kind, list):
                widget = QComboBox()
                canonical_items(widget, kind)
                widget.currentIndexChanged.connect(self.queue)
            else:
                widget = self._spin(kind)
            self.controls[key] = widget
            form.addRow(text, widget)
        layout.addWidget(group)

    def style(self):
        data = default_style()
        for key, widget in self.controls.items():
            if isinstance(widget, QCheckBox):
                data[key] = widget.isChecked()
            elif isinstance(widget, ColorButton):
                data[key] = widget.value
            elif isinstance(widget, QComboBox):
                data[key] = widget.currentData()
            else:
                data[key] = widget.value()
        data['label_color'] = 'auto' if self.auto_label_color.isChecked() else self.label_color.value
        for kind, (color, radius, dashes) in self.contact_controls.items():
            data['contacts'][kind] = dict(color=color.value, radius=radius.value(), dashes=dashes.value())
        return data

    def set_style(self, data, apply=True):
        if not isinstance(data, dict):
            raise ValueError(self.tr('A style must be a JSON object.'))
        defaults = default_style()
        defaults.update({k: v for k, v in data.items() if k in defaults and k != 'contacts'})
        contacts = data.get('contacts', {})
        if not isinstance(contacts, dict):
            raise ValueError(self.tr('Invalid interaction styles.'))
        for kind in KINDS:
            defaults['contacts'][kind].update(contacts.get(kind, {}))
        # Validate first, so a rejected file cannot partially apply or run a command.
        for key, widget in self.controls.items():
            value = defaults[key]
            if isinstance(widget, QComboBox) and widget.findData(str(value)) < 0:
                raise ValueError(self.tr('Unsupported {key}: {value}', key=key, value=value))
            if isinstance(widget, ColorButton) and not QColor(str(value)).isValid():
                raise ValueError(self.tr('Invalid {key}', key=key))
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                if not isinstance(value, (int, float)) or not widget.minimum() <= value <= widget.maximum():
                    raise ValueError(self.tr('{key} is outside the supported range', key=key))
            if isinstance(widget, QCheckBox) and not isinstance(value, bool):
                raise ValueError(self.tr('{key} must be true or false', key=key))
        if defaults['label_color'] != 'auto' and not QColor(str(defaults['label_color'])).isValid():
            raise ValueError(self.tr('Invalid label color'))
        for values in defaults['contacts'].values():
            if not QColor(str(values['color'])).isValid() or not 0.02 <= float(values['radius']) <= 0.4:
                raise ValueError(self.tr('Invalid interaction color or radius'))
            if not isinstance(values['dashes'], int) or not 0 <= values['dashes'] <= 20:
                raise ValueError(self.tr('Dash count must be an integer from 0 to 20'))
        self.loading = True
        try:
            for key, widget in self.controls.items():
                value = defaults[key]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(value)
                elif isinstance(widget, ColorButton):
                    widget.set_value(value)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(widget.findData(value))
                else:
                    widget.setValue(value)
            self.auto_label_color.setChecked(defaults['label_color'] == 'auto')
            if defaults['label_color'] != 'auto':
                self.label_color.set_value(defaults['label_color'])
            for kind, (color, radius, dashes) in self.contact_controls.items():
                values = defaults['contacts'][kind]
                color.set_value(values['color'])
                radius.setValue(float(values['radius']))
                dashes.setValue(values['dashes'])
        finally:
            self.loading = False
        if apply:
            self.apply()

    def queue(self, *args):
        if not self.loading:
            self.timer.start(150)

    def apply(self):
        self.timer.stop()
        if self.tool._closed:
            return
        try:
            apply_scene(self.tool.session, self.style())
            self.tool._refresh()
            self.feedback.setText('')
        except Exception as err:
            self.tool.status.setText(str(err))
            self.feedback.setText(str(err))

    def _move_labels(self, enabled):
        modes = self.tool.session.ui.mouse_modes
        if enabled:
            self._previous_mouse_mode = modes.mode('right', exact=True)
            mode = modes.named_mode('move label')
            if mode is None:
                from chimerax.label.movelabel import MoveLabelMouseMode
                mode = MoveLabelMouseMode(self.tool.session)
                modes.add_mode(mode)
            modes.bind_mouse_mode(mouse_button='right', mouse_modifiers=[], mode=mode)
            self._owns_mouse_mode = True
        elif self._owns_mouse_mode:
            current = modes.mode('right', exact=True)
            if current is not None and current.name == 'move label':
                if self._previous_mouse_mode is None:
                    modes.remove_binding(button='right', modifiers=[])
                else:
                    modes.bind_mouse_mode(mouse_button='right', mouse_modifiers=[], mode=self._previous_mouse_mode)
            self._owns_mouse_mode = False

    def close(self):
        self.timer.stop()
        self._move_labels(False)

    def apply_result(self):
        result = self.tool.result
        index = self.tool.sites.currentIndex()
        if result and index >= 0:
            self.presentation.apply(result, result[0].sites[index],
                {k: w.isChecked() for k, w in self.tool.filters.items()}, self.style())

    def save_default(self):
        get_settings(self.tool.session).appearance = json.dumps(self.style())
        self.tool.language.message(self.tool.status, 'Appearance saved as the default for new PLIP-Xplorer panels.')

    def save_style(self):
        path, _ = QFileDialog.getSaveFileName(self.widget, self.tr('Save style'), 'plip-style.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(self.style(), indent=2), encoding='utf-8')
            except OSError as err:
                self.tool.status.setText(str(err))

    def load_style(self):
        path, _ = QFileDialog.getOpenFileName(self.widget, self.tr('Load style'), '', 'JSON (*.json)')
        if path:
            try:
                self.set_style(json.loads(Path(path).read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, KeyError) as err:
                self.tool.language.message(self.tool.status, 'Cannot load style: {error}', error=str(err))

    def _build_export(self, tabs):
        widget = QWidget()
        body = QVBoxLayout(widget)
        note = QLabel('Export the current camera view. Rotate/zoom in ChimeraX before saving. '
                      'Transparent backgrounds are available for PNG and TIFF.')
        note.setWordWrap(True)
        body.addWidget(note)
        form = QFormLayout()
        self.image_format = QComboBox()
        self.image_format.addItems(['PNG', 'TIFF', 'JPEG'])
        form.addRow('Format', self.image_format)
        self.width = QSpinBox()
        self.width.setRange(64, 8192)
        self.width.setValue(2400)
        self.height = QSpinBox()
        self.height.setRange(64, 8192)
        self.height.setValue(1800)
        form.addRow('Width (pixels)', self.width)
        form.addRow('Height (pixels)', self.height)
        self.aspect = QCheckBox('Keep current viewport aspect ratio')
        self.aspect.setChecked(True)
        self.height.setEnabled(False)
        self.aspect.toggled.connect(lambda checked: self.height.setEnabled(not checked))
        form.addRow(self.aspect)
        self.supersample = QSpinBox()
        self.supersample.setRange(1, 4)
        self.supersample.setValue(3)
        form.addRow('Antialiasing (supersampling)', self.supersample)
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(95)
        form.addRow('JPEG quality', self.quality)
        self.transparent = QCheckBox('Transparent background')
        form.addRow(self.transparent)
        self.only_result = QCheckBox('Only the current PLIP structure and its drawings')
        self.only_result.setChecked(True)
        form.addRow(self.only_result)
        body.addLayout(form)
        def format_changed(*args):
            jpeg = self.image_format.currentText() == 'JPEG'
            self.transparent.setEnabled(not jpeg)
            if jpeg:
                self.transparent.setChecked(False)
            self.quality.setEnabled(jpeg)
        self.image_format.currentIndexChanged.connect(format_changed)
        format_changed()
        button = QPushButton('Export image…')
        button.clicked.connect(self.save_image)
        body.addWidget(button)
        self.export_status = QLabel('Resolution is specified in pixels, independent of monitor size.')
        self.export_status.setWordWrap(True)
        body.addWidget(self.export_status)
        body.addStretch(1)
        tabs.addTab(widget, 'Export image')

    def save_image(self):
        if not self.tool.result:
            self.tool.language.message(self.export_status, 'Load or analyze a PLIP result first.')
            return
        fmt = self.image_format.currentText()
        ext = dict(PNG='png', TIFF='tiff', JPEG='jpg')[fmt]
        path, _ = QFileDialog.getSaveFileName(self.widget, self.tr('Export image'), f'plip.{ext}', f'{fmt} (*.{ext})')
        if not path:
            return
        if not Path(path).suffix:
            path += '.' + ext
        try:
            self.export_to(path)
            self.tool.language.message(self.export_status, 'Image saved: {path}', path=path)
        except Exception as err:
            self.export_status.setText(str(err))

    def export_to(self, path):
        if self.timer.isActive():
            self.apply()
        width, height = self.width.value(), self.height.value()
        if self.aspect.isChecked():
            w, h = self.tool.session.main_view.window_size
            height = max(1, round(width * h / max(w, 1)))
            self.height.setValue(height)
        export_image(self.tool.session, self.tool.result, path, width=width, height=height,
                     supersample=self.supersample.value(), transparent=self.transparent.isChecked(),
                     quality=self.quality.value(), only_result=self.only_result.isChecked())
