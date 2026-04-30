"""Parameter editing panel for model components."""
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QScrollArea,
    QSizePolicy, QFrame, QToolButton,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator

from .model_registry import MODELS, LINE_PRESETS, COMPONENT_COLORS, get_param_role


class ParamEditor(QWidget):
    """Editor for a single model parameter with expandable bounds/fixed controls."""

    value_changed = pyqtSignal(str, float)
    bounds_changed = pyqtSignal(str, float, float)
    fixed_changed = pyqtSignal(str, bool)

    def __init__(self, param_name, model, model_name, parent=None):
        super().__init__(parent)
        self.param_name = param_name
        self.model = model
        self.model_name = model_name
        self._updating = False
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(2, 1, 2, 1)

        role = get_param_role(model_name, param_name)
        label_text = param_name
        if role:
            label_text += f' ({role})'
        self.label = QLabel(label_text)
        self.label.setFixedWidth(140)
        self.label.setToolTip(f'Role: {role}' if role else param_name)

        param = getattr(model, param_name)
        self._param = param

        self.edit = QLineEdit(f'{param.value:.6g}')
        self.edit.setFixedWidth(120)
        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.ScientificNotation)
        self.edit.setValidator(validator)

        if param.fixed:
            self.edit.setStyleSheet(
                'background-color: #fff8dc; color: #333333;'
            )

        self.edit.editingFinished.connect(self._on_edit)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setText('▸')
        self.toggle_btn.setFixedSize(18, 18)
        self.toggle_btn.setStyleSheet('QToolButton { border: none; font-size: 10px; }')
        self.toggle_btn.clicked.connect(self._toggle_expand)

        main_row.addWidget(self.toggle_btn)
        main_row.addWidget(self.label)
        main_row.addWidget(self.edit)

        lb, ub = param.bounds
        bound_str = ''
        if lb is not None or ub is not None:
            lb_s = f'{lb}' if lb is not None else ''
            ub_s = f'{ub}' if ub is not None else ''
            bound_str = f'[{lb_s}, {ub_s}]'
        if bound_str:
            blabel = QLabel(bound_str)
            blabel.setStyleSheet('color: gray; font-size: 9px;')
            main_row.addWidget(blabel)

        outer.addLayout(main_row)

        self._detail_widget = QWidget()
        detail_layout = QHBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(22, 1, 2, 1)
        detail_layout.setSpacing(4)

        detail_layout.addWidget(QLabel('Lo:'))
        self.lo_edit = QLineEdit()
        self.lo_edit.setFixedWidth(70)
        vlo = QDoubleValidator()
        vlo.setNotation(QDoubleValidator.ScientificNotation)
        self.lo_edit.setValidator(vlo)
        self.lo_edit.setText(f'{lb:.6g}' if lb is not None else '')
        detail_layout.addWidget(self.lo_edit)

        detail_layout.addWidget(QLabel('Hi:'))
        self.hi_edit = QLineEdit()
        self.hi_edit.setFixedWidth(70)
        vhi = QDoubleValidator()
        vhi.setNotation(QDoubleValidator.ScientificNotation)
        self.hi_edit.setValidator(vhi)
        self.hi_edit.setText(f'{ub:.6g}' if ub is not None else '')
        detail_layout.addWidget(self.hi_edit)

        self.apply_bounds_btn = QPushButton('Set')
        self.apply_bounds_btn.setFixedSize(32, 20)
        self.apply_bounds_btn.setStyleSheet('font-size: 9px;')
        self.apply_bounds_btn.clicked.connect(self._on_apply_bounds)
        detail_layout.addWidget(self.apply_bounds_btn)

        detail_layout.addSpacing(6)

        self.fixed_check = QCheckBox('Fixed')
        self.fixed_check.setChecked(param.fixed)
        self.fixed_check.stateChanged.connect(self._on_fixed_changed)
        detail_layout.addWidget(self.fixed_check)

        detail_layout.addStretch()
        self._detail_widget.setVisible(False)
        outer.addWidget(self._detail_widget)

    def update_value(self, value):
        self._updating = True
        self.edit.setText(f'{value:.6g}')
        self._updating = False

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._detail_widget.setVisible(self._expanded)
        self.toggle_btn.setText('▾' if self._expanded else '▸')

    def _on_edit(self):
        if self._updating:
            return
        try:
            val = float(self.edit.text())
            self.value_changed.emit(self.param_name, val)
        except ValueError:
            pass

    def _on_apply_bounds(self):
        lo = self._parse(self.lo_edit.text())
        hi = self._parse(self.hi_edit.text())
        if lo is None:
            lo = -1e10
        if hi is None:
            hi = 1e10
        self._param.bounds = (lo, hi)
        self.bounds_changed.emit(self.param_name, lo, hi)

    def _on_fixed_changed(self, state):
        fixed = state == Qt.Checked
        self._param.fixed = fixed
        if fixed:
            self.edit.setStyleSheet(
                'background-color: #fff8dc; color: #333333;'
            )
        else:
            self.edit.setStyleSheet('')
        self.fixed_changed.emit(self.param_name, fixed)

    @staticmethod
    def _parse(text):
        try:
            return float(text)
        except (ValueError, TypeError):
            return None


class ComponentPanel(QGroupBox):
    """Panel for a single model component with all its parameters."""

    parameter_changed = pyqtSignal(int, str, float)
    visibility_changed = pyqtSignal(int, bool)
    remove_requested = pyqtSignal(int)
    absorption_targets_changed = pyqtSignal(int, list)

    def __init__(self, index, comp, all_components, parent=None):
        super().__init__(parent)
        self.index = index
        self.comp = comp
        self._editors = {}
        self._target_checks = {}

        color = COMPONENT_COLORS[index % len(COMPONENT_COLORS)]
        self.setTitle(f'')
        self.setStyleSheet(
            f'ComponentPanel {{ border: 2px solid {color}; border-radius: 4px; '
            f'margin-top: 8px; padding-top: 8px; }}'
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        self.vis_check = QCheckBox()
        self.vis_check.setChecked(comp['visible'])
        self.vis_check.stateChanged.connect(self._on_visibility)
        header.addWidget(self.vis_check)

        name_label = QLabel(comp['name'])
        name_label.setStyleSheet(f'color: {color}; font-weight: bold;')
        header.addWidget(name_label)
        header.addStretch()

        remove_btn = QPushButton('✕')
        remove_btn.setFixedSize(22, 22)
        remove_btn.setStyleSheet('QPushButton { border: none; color: red; font-weight: bold; }')
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.index))
        header.addWidget(remove_btn)

        layout.addLayout(header)

        model = comp['model']
        model_name = comp['model_name']

        for pname in model.param_names:
            editor = ParamEditor(pname, model, model_name)
            editor.value_changed.connect(self._on_param_changed)
            editor.bounds_changed.connect(self._on_bounds_changed)
            editor.fixed_changed.connect(self._on_fixed_changed)
            self._editors[pname] = editor
            layout.addWidget(editor)

        info = MODELS.get(model_name)
        if info is not None and info['category'] == 'absorption':
            self._build_target_selector(layout, all_components)

    def _build_target_selector(self, layout, all_components):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        target_label = QLabel('Absorbs:')
        target_label.setStyleSheet('font-weight: bold; font-size: 10px;')
        layout.addWidget(target_label)

        absorbs = self.comp.get('absorbs', set())

        for i, other in enumerate(all_components):
            if i == self.index:
                continue
            other_info = MODELS.get(other['model_name'])
            if other_info is not None and other_info['category'] == 'absorption':
                continue

            cb = QCheckBox(other['name'])
            other_color = COMPONENT_COLORS[i % len(COMPONENT_COLORS)]
            cb.setStyleSheet(f'color: {other_color};')
            cb.setChecked(i in absorbs)
            cb.stateChanged.connect(lambda state, idx=i: self._on_target_changed(idx, state))
            self._target_checks[i] = cb
            layout.addWidget(cb)

    def refresh_targets(self, all_components):
        parent_layout = self.layout()
        absorbs = self.comp.get('absorbs', set())

        for i, other in enumerate(all_components):
            if i == self.index:
                continue
            other_info = MODELS.get(other['model_name'])
            if other_info is not None and other_info['category'] == 'absorption':
                continue

            if i in self._target_checks:
                cb = self._target_checks[i]
                cb.blockSignals(True)
                cb.setChecked(i in absorbs)
                cb.setText(other['name'])
                other_color = COMPONENT_COLORS[i % len(COMPONENT_COLORS)]
                cb.setStyleSheet(f'color: {other_color};')
                cb.blockSignals(False)
            else:
                cb = QCheckBox(other['name'])
                other_color = COMPONENT_COLORS[i % len(COMPONENT_COLORS)]
                cb.setStyleSheet(f'color: {other_color};')
                cb.setChecked(i in absorbs)
                cb.stateChanged.connect(lambda state, idx=i: self._on_target_changed(idx, state))
                self._target_checks[i] = cb
                parent_layout.addWidget(cb)

        stale = [k for k in self._target_checks if k >= len(all_components) or k == self.index]
        for k in stale:
            cb = self._target_checks.pop(k)
            parent_layout.removeWidget(cb)
            cb.deleteLater()

    def _on_target_changed(self, target_idx, state):
        absorbs = self.comp.get('absorbs', set())
        if state == Qt.Checked:
            absorbs.add(target_idx)
        else:
            absorbs.discard(target_idx)
        self.comp['absorbs'] = absorbs
        self.absorption_targets_changed.emit(self.index, sorted(absorbs))

    def update_param(self, param_name, value):
        if param_name in self._editors:
            self._editors[param_name].update_value(value)

    def _on_param_changed(self, param_name, value):
        self.parameter_changed.emit(self.index, param_name, value)

    def _on_bounds_changed(self, param_name, lo, hi):
        pass

    def _on_fixed_changed(self, param_name, fixed):
        pass

    def _on_visibility(self, state):
        self.visibility_changed.emit(self.index, state == Qt.Checked)


class ParamPanel(QWidget):
    """Scrollable panel containing all model component editors."""

    add_requested = pyqtSignal(str, float)
    remove_requested = pyqtSignal(int)
    parameter_changed = pyqtSignal(int, str, float)
    visibility_changed = pyqtSignal(int, bool)
    absorption_targets_changed = pyqtSignal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(450)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        add_row = QHBoxLayout()
        self.model_combo = QComboBox()
        for name in MODELS:
            self.model_combo.addItem(name)
        add_row.addWidget(self.model_combo)

        self.preset_combo = QComboBox()
        for name in LINE_PRESETS:
            self.preset_combo.addItem(name)
        add_row.addWidget(self.preset_combo)

        self.add_btn = QPushButton('+ Add')
        self.add_btn.clicked.connect(self._on_add)
        add_row.addWidget(self.add_btn)

        main_layout.addLayout(add_row)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setAlignment(Qt.AlignTop)
        self._scroll_layout.setSpacing(4)
        self._scroll_area.setWidget(self._scroll_content)
        main_layout.addWidget(self._scroll_area, stretch=1)

        self._component_panels = {}

    def _on_add(self):
        model_name = self.model_combo.currentText()
        preset_name = self.preset_combo.currentText()
        wavec = LINE_PRESETS.get(preset_name)
        self.add_requested.emit(model_name, wavec if wavec else 0.0)

    def add_component(self, index, comp, all_components):
        panel = ComponentPanel(index, comp, all_components)
        panel.parameter_changed.connect(self.parameter_changed.emit)
        panel.visibility_changed.connect(self.visibility_changed.emit)
        panel.remove_requested.connect(self.remove_requested.emit)
        panel.absorption_targets_changed.connect(self.absorption_targets_changed.emit)
        self._component_panels[index] = panel
        self._scroll_layout.addWidget(panel)

    def refresh_absorption_targets(self, all_components):
        for idx, panel in self._component_panels.items():
            info = MODELS.get(all_components[idx]['model_name'] if idx < len(all_components) else '')
            if info is not None and info['category'] == 'absorption':
                panel.refresh_targets(all_components)

    def remove_component(self, index):
        if index in self._component_panels:
            panel = self._component_panels.pop(index)
            self._scroll_layout.removeWidget(panel)
            panel.deleteLater()

        new_panels = {}
        for old_idx, panel in sorted(self._component_panels.items()):
            new_idx = old_idx if old_idx < index else old_idx - 1
            panel.index = new_idx
            new_panels[new_idx] = panel
        self._component_panels = new_panels

    def update_param_value(self, index, param_name, value):
        if index in self._component_panels:
            self._component_panels[index].update_param(param_name, value)

    def clear_all(self):
        for panel in self._component_panels.values():
            self._scroll_layout.removeWidget(panel)
            panel.deleteLater()
        self._component_panels = {}
