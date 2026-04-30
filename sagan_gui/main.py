"""Main window for SAGAN GUI."""
import sys
import os
import json
import pickle
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog, QSplitter, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QProgressBar, QLabel, QSpinBox, QGroupBox,
    QMessageBox, QStatusBar, QLineEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

from .spectrum_loader import load_spectrum
from .model_registry import MODELS, create_model, COMPONENT_COLORS
from .canvas import SpectrumCanvas
from .drag_handler import DragHandler
from .param_panel import ParamPanel
from .fitting_worker import FittingWorker
from .post_mcmc import CornerPlotDialog, compute_confidence_band


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('SAGAN GUI — Spectral Analysis')
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)

        self.spectrum = None
        self._observed_spectrum = None
        self._z = 0.0
        self._in_rest_frame = False
        self._components = []
        self._component_counter = 0
        self._fitting_worker = None
        self._last_samples = None
        self._last_param_names = None
        self._last_chi2_r = None
        self._last_bic = None
        self._flux_scale = 1.0
        self._flux_scale_exp = 0

        self._init_ui()
        self._init_menu()
        self._connect_signals()

        self.statusBar().showMessage('Ready. Open a spectrum to begin.')

    def _init_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        self.canvas = SpectrumCanvas()
        splitter.addWidget(self.canvas)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.param_panel = ParamPanel()
        right_layout.addWidget(self.param_panel, stretch=1)

        range_group = QGroupBox('Display Range')
        range_layout = QVBoxLayout(range_group)
        range_layout.setSpacing(3)

        z_row = QHBoxLayout()
        z_row.addWidget(QLabel('Redshift z:'))
        self.z_edit = QLineEdit('0')
        self.z_edit.setFixedWidth(90)
        vz = QDoubleValidator()
        vz.setNotation(QDoubleValidator.ScientificNotation)
        vz.setBottom(0)
        self.z_edit.setValidator(vz)
        z_row.addWidget(self.z_edit)
        self.apply_z_btn = QPushButton('To Rest Frame')
        self.apply_z_btn.clicked.connect(self._apply_redshift)
        z_row.addWidget(self.apply_z_btn)
        self.obs_frame_btn = QPushButton('To Observed')
        self.obs_frame_btn.clicked.connect(self._to_observed_frame)
        z_row.addWidget(self.obs_frame_btn)
        range_layout.addLayout(z_row)

        wave_row = QHBoxLayout()
        wave_row.addWidget(QLabel('λ min:'))
        self.wave_min_edit = QLineEdit()
        self.wave_min_edit.setFixedWidth(90)
        v1 = QDoubleValidator()
        v1.setNotation(QDoubleValidator.ScientificNotation)
        self.wave_min_edit.setValidator(v1)
        wave_row.addWidget(self.wave_min_edit)
        wave_row.addWidget(QLabel('λ max:'))
        self.wave_max_edit = QLineEdit()
        self.wave_max_edit.setFixedWidth(90)
        v2 = QDoubleValidator()
        v2.setNotation(QDoubleValidator.ScientificNotation)
        self.wave_max_edit.setValidator(v2)
        wave_row.addWidget(self.wave_max_edit)
        range_layout.addLayout(wave_row)

        y_row = QHBoxLayout()
        y_row.addWidget(QLabel('Y min:'))
        self.y_min_edit = QLineEdit()
        self.y_min_edit.setFixedWidth(90)
        v3 = QDoubleValidator()
        v3.setNotation(QDoubleValidator.ScientificNotation)
        self.y_min_edit.setValidator(v3)
        y_row.addWidget(self.y_min_edit)
        y_row.addWidget(QLabel('Y max:'))
        self.y_max_edit = QLineEdit()
        self.y_max_edit.setFixedWidth(90)
        v4 = QDoubleValidator()
        v4.setNotation(QDoubleValidator.ScientificNotation)
        self.y_max_edit.setValidator(v4)
        y_row.addWidget(self.y_max_edit)
        range_layout.addLayout(y_row)

        res_y_row = QHBoxLayout()
        res_y_row.addWidget(QLabel('Res Y min:'))
        self.res_y_min_edit = QLineEdit('-10')
        self.res_y_min_edit.setFixedWidth(90)
        v5 = QDoubleValidator()
        v5.setNotation(QDoubleValidator.ScientificNotation)
        self.res_y_min_edit.setValidator(v5)
        res_y_row.addWidget(self.res_y_min_edit)
        res_y_row.addWidget(QLabel('Res Y max:'))
        self.res_y_max_edit = QLineEdit('10')
        self.res_y_max_edit.setFixedWidth(90)
        v6 = QDoubleValidator()
        v6.setNotation(QDoubleValidator.ScientificNotation)
        self.res_y_max_edit.setValidator(v6)
        res_y_row.addWidget(self.res_y_max_edit)
        range_layout.addLayout(res_y_row)

        range_btn_row = QHBoxLayout()
        self.set_range_btn = QPushButton('Set Range')
        self.set_range_btn.clicked.connect(self._set_display_range)
        range_btn_row.addWidget(self.set_range_btn)
        self.auto_range_btn = QPushButton('Auto Fit')
        self.auto_range_btn.clicked.connect(self._auto_fit_range)
        range_btn_row.addWidget(self.auto_range_btn)
        self.from_zoom_btn = QPushButton('From Zoom')
        self.from_zoom_btn.clicked.connect(self._range_from_zoom)
        range_btn_row.addWidget(self.from_zoom_btn)
        range_layout.addLayout(range_btn_row)

        right_layout.addWidget(range_group)

        fit_group = QGroupBox('MCMC Fitting')
        fit_layout = QVBoxLayout(fit_group)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel('Walkers:'))
        self.walkers_spin = QSpinBox()
        self.walkers_spin.setRange(10, 500)
        self.walkers_spin.setValue(50)
        settings_row.addWidget(self.walkers_spin)
        settings_row.addWidget(QLabel('Steps:'))
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(100, 100000)
        self.steps_spin.setValue(6000)
        self.steps_spin.setSingleStep(1000)
        settings_row.addWidget(self.steps_spin)
        settings_row.addWidget(QLabel('Burn-in:'))
        self.burnin_spin = QSpinBox()
        self.burnin_spin.setRange(0, 50000)
        self.burnin_spin.setValue(2000)
        self.burnin_spin.setSingleStep(500)
        settings_row.addWidget(self.burnin_spin)
        fit_layout.addLayout(settings_row)

        btn_row = QHBoxLayout()
        self.fit_btn = QPushButton('Run MCMC')
        self.fit_btn.setEnabled(False)
        btn_row.addWidget(self.fit_btn)

        self.stop_btn = QPushButton('Stop')
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.corner_btn = QPushButton('Corner Plot')
        self.corner_btn.setEnabled(False)
        btn_row.addWidget(self.corner_btn)

        self.save_btn = QPushButton('Save Results')
        self.save_btn.setEnabled(False)
        btn_row.addWidget(self.save_btn)

        self.load_results_btn = QPushButton('Load Results')
        btn_row.addWidget(self.load_results_btn)

        fit_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        fit_layout.addWidget(self.progress_bar)

        right_layout.addWidget(fit_group)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.drag_handler = DragHandler(self.canvas)

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('&File')
        open_action = QAction('&Open Spectrum...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self._open_spectrum)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction('E&xit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu('&View')
        reset_zoom = QAction('Reset &Zoom', self)
        reset_zoom.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom)

        fit_menu = menubar.addMenu('&Fit')
        run_mcmc = QAction('Run &MCMC', self)
        run_mcmc.setShortcut('Ctrl+M')
        run_mcmc.triggered.connect(self._run_mcmc)
        fit_menu.addAction(run_mcmc)

        show_corner = QAction('Show &Corner Plot', self)
        show_corner.triggered.connect(self._show_corner)
        fit_menu.addAction(show_corner)

    def _connect_signals(self):
        self.param_panel.add_requested.connect(self._add_component)
        self.param_panel.remove_requested.connect(self._remove_component)
        self.param_panel.parameter_changed.connect(self._on_param_changed)
        self.param_panel.visibility_changed.connect(self._on_visibility_changed)
        self.param_panel.absorption_targets_changed.connect(self._on_absorption_targets_changed)

        self.drag_handler.parameter_changed.connect(self._on_drag_param_changed)
        self.drag_handler.drag_started.connect(self._on_drag_started)
        self.drag_handler.drag_ended.connect(self._on_drag_ended)

        self.fit_btn.clicked.connect(self._run_mcmc)
        self.stop_btn.clicked.connect(self._stop_mcmc)
        self.corner_btn.clicked.connect(self._show_corner)
        self.save_btn.clicked.connect(self._save_results)
        self.load_results_btn.clicked.connect(self._load_results)

    def _open_spectrum(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, 'Open Spectrum', '',
            'FITS files (*.fits *.fit);;All files (*)',
        )
        if not filepath:
            return

        try:
            result = load_spectrum(filepath)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load spectrum:\n{e}')
            return

        self.spectrum = result
        wave = result['wave']
        flux_ujy = result['flux']
        err_ujy = result['err']

        c_A = 2.998e18
        flam = flux_ujy * 1e-29 * c_A / wave ** 2
        elam = err_ujy * 1e-29 * c_A / wave ** 2

        self._observed_spectrum = {
            'wave': wave.copy(),
            'flux': flam.copy(),
            'err': elam.copy(),
        }
        self._in_rest_frame = False
        self.z_edit.setText('0')

        self._flux_scale, self._flux_scale_exp = self._compute_flux_scale(flam)

        self.spectrum = {
            'wave': wave.copy(),
            'flux': flam / self._flux_scale,
            'err': elam / self._flux_scale,
        }
        flux = self.spectrum['flux']
        err = self.spectrum['err']

        self.canvas.clear_all()
        self.canvas.plot_spectrum(wave, flux, err)
        self._update_ylabel()

        meta = result.get('metadata', {})
        obj = meta.get('object', os.path.basename(filepath))
        self.statusBar().showMessage(
            f'Loaded: {obj} | {len(wave)} points | '
            f'wave: {wave[0]:.1f}–{wave[-1]:.1f} Å'
        )

        self._update_drag_components()
        self._auto_fit_range()
        self._update_xlabel()

    def _add_component(self, model_name, wavec):
        if self.spectrum is None:
            QMessageBox.warning(self, 'Warning', 'Open a spectrum first.')
            return

        wave = self.spectrum['wave']
        if wavec == 0.0:
            wavec = float(np.mean(wave))

        wave_range = self.canvas.get_visible_range()
        model = create_model(model_name, wavec=wavec, wave_range=wave_range)

        idx = self._component_counter
        self._component_counter += 1

        info = MODELS[model_name]
        display = f'{model_name} #{idx}'
        if info['has_wavec'] and wavec:
            display = f'{model_name} ({wavec:.1f})'

        color = COMPONENT_COLORS[len(self._components) % len(COMPONENT_COLORS)]

        comp = {
            'id': idx,
            'name': display,
            'model_name': model_name,
            'model': model,
            'visible': True,
            'color': color,
        }

        if info['category'] == 'absorption':
            absorbs = set()
            for i, c in enumerate(self._components):
                c_info = MODELS.get(c['model_name'])
                if c_info is None or c_info['category'] != 'absorption':
                    absorbs.add(i)
            comp['absorbs'] = absorbs

        self._components.append(comp)

        panel_idx = len(self._components) - 1
        self.param_panel.add_component(panel_idx, comp, self._components)
        self._refresh_absorption_panels()
        self._update_drag_components()
        self._update_canvas()
        self._update_fit_button()

        self.statusBar().showMessage(f'Added: {display}')

    def _remove_component(self, panel_idx):
        if panel_idx < 0 or panel_idx >= len(self._components):
            return

        self._components.pop(panel_idx)
        self.param_panel.remove_component(panel_idx)

        for comp in self._components:
            if 'absorbs' in comp:
                new_absorbs = set()
                for old_idx in comp['absorbs']:
                    if old_idx < panel_idx:
                        new_absorbs.add(old_idx)
                    elif old_idx > panel_idx:
                        new_absorbs.add(old_idx - 1)
                comp['absorbs'] = new_absorbs

        self._refresh_absorption_panels()
        self._update_drag_components()
        self._update_canvas()
        self._update_fit_button()

        self.statusBar().showMessage(f'Removed component {panel_idx}')

    def _on_param_changed(self, panel_idx, param_name, value):
        if panel_idx >= len(self._components):
            return
        comp = self._components[panel_idx]
        model = comp['model']
        param = getattr(model, param_name)

        lb, ub = param.bounds
        if lb is not None and value < lb:
            value = float(lb)
        if ub is not None and value > ub:
            value = float(ub)

        param.value = value
        self._update_canvas_single(panel_idx)

    def _on_drag_param_changed(self, panel_idx, param_name, value):
        if panel_idx >= len(self._components):
            return
        comp = self._components[panel_idx]
        model = comp['model']
        param = getattr(model, param_name)

        lb, ub = param.bounds
        if lb is not None and value < lb:
            value = float(lb)
        if ub is not None and value > ub:
            value = float(ub)

        param.value = value
        self.param_panel.update_param_value(panel_idx, param_name, value)
        self._update_canvas_single(panel_idx)

    def _on_visibility_changed(self, panel_idx, visible):
        if panel_idx < len(self._components):
            self._components[panel_idx]['visible'] = visible
            self._update_drag_components()
            self._update_canvas()

    def _on_absorption_targets_changed(self, abs_idx, target_list):
        if abs_idx < len(self._components):
            self._components[abs_idx]['absorbs'] = set(target_list)
            self._update_canvas()

    def _refresh_absorption_panels(self):
        self.param_panel.refresh_absorption_targets(self._components)

    def _on_drag_started(self, idx):
        pass

    def _on_drag_ended(self):
        pass

    def _update_drag_components(self):
        self.drag_handler.set_components(self._components)

    def _get_wave_for_eval(self):
        if self.spectrum is None:
            return None
        return self.spectrum['wave']

    def _update_canvas(self):
        wave = self._get_wave_for_eval()
        if wave is None:
            return
        self.canvas.plot_components(self._components, wave)
        self._update_live_stats()

    def _update_canvas_single(self, idx):
        wave = self._get_wave_for_eval()
        if wave is None:
            return
        if idx < len(self._components):
            self.canvas.update_single_component(idx, self._components[idx], wave)
        self._update_live_stats()

    def _update_live_stats(self):
        visible = [c for c in self._components if c['visible']]
        if not visible or self.spectrum is None:
            return
        wave_use, flux_use, err_use = self._get_fit_region()
        if wave_use is None or len(wave_use) == 0:
            return
        mask = np.isfinite(flux_use) & np.isfinite(err_use) & (err_use > 0)
        if not np.any(mask):
            return
        composite = self.canvas._compute_composite(wave_use)
        residual = flux_use - composite
        chi2 = np.sum((residual[mask] / err_use[mask]) ** 2)
        n_data = int(np.sum(mask))
        n_params = 0
        for comp in visible:
            for pname in comp['model'].param_names:
                p = getattr(comp['model'], pname)
                if not p.fixed and not p.tied:
                    n_params += 1
        dof = max(n_data - n_params, 1)
        chi2_r = chi2 / dof
        bic = chi2 + n_params * np.log(n_data)
        self.canvas.show_stats(chi2_r, bic)

    def _update_fit_button(self):
        visible = [c for c in self._components if c['visible']]
        self.fit_btn.setEnabled(len(visible) > 0 and self.spectrum is not None)

    def _compute_fit_stats(self, model):
        wave_use, flux_use, err_use = self._get_fit_region()
        if wave_use is None or len(wave_use) == 0:
            return 0.0, 0.0, 0, 0
        try:
            model_flux = model(wave_use)
        except Exception:
            return 0.0, 0.0, len(wave_use), 0

        mask = np.isfinite(flux_use) & np.isfinite(err_use) & (err_use > 0)
        n_data = int(np.sum(mask))
        if n_data == 0:
            return 0.0, 0.0, 0, 0

        chi2 = np.sum(((flux_use[mask] - model_flux[mask]) / err_use[mask]) ** 2)

        n_params = 0
        for pname in model.param_names:
            p = getattr(model, pname)
            if not p.fixed and not p.tied:
                n_params += 1

        dof = max(n_data - n_params, 1)
        chi2_r = chi2 / dof
        bic = chi2 + n_params * np.log(n_data)

        return float(chi2_r), float(bic), n_data, n_params

    def _build_composite_model(self):
        additive = [(i, c) for i, c in enumerate(self._components) if c['visible']
                     and MODELS.get(c['model_name'], {}).get('category') != 'absorption']
        absorptions = [(i, c) for i, c in enumerate(self._components) if c['visible']
                       and MODELS.get(c['model_name'], {}).get('category') == 'absorption']

        if not additive:
            return None

        if not absorptions:
            composite = None
            for _, comp in additive:
                if composite is None:
                    composite = comp['model']
                else:
                    composite = composite + comp['model']
            return composite

        groups = {}
        for add_i, add_comp in additive:
            key = frozenset(
                abs_i for abs_i, abs_comp in absorptions
                if abs_comp.get('absorbs') is None or add_i in abs_comp['absorbs']
            )
            groups.setdefault(key, []).append(add_comp['model'])

        composite = None
        for abs_key, models in groups.items():
            group_sum = None
            for m in models:
                if group_sum is None:
                    group_sum = m
                else:
                    group_sum = group_sum + m

            for abs_i in sorted(abs_key):
                group_sum = group_sum * self._components[abs_i]['model']

            if composite is None:
                composite = group_sum
            else:
                composite = composite + group_sum

        return composite

    def _get_fit_region(self):
        if self.spectrum is None:
            return None, None, None

        wave = self.spectrum['wave']
        flux = self.spectrum['flux']
        err = self.spectrum['err']

        xmin, xmax = self.canvas.get_visible_range()
        mask = (wave >= xmin) & (wave <= xmax) & np.isfinite(flux) & np.isfinite(err) & (err > 0)

        if not np.any(mask):
            mask = np.isfinite(flux) & np.isfinite(err) & (err > 0)

        return wave[mask], flux[mask], err[mask]

    def _run_mcmc(self):
        composite = self._build_composite_model()
        if composite is None:
            QMessageBox.warning(self, 'Warning', 'No visible components to fit.')
            return

        wave_use, flux_use, err_use = self._get_fit_region()
        if wave_use is None or len(wave_use) == 0:
            QMessageBox.warning(self, 'Warning', 'No valid data in the visible range.')
            return

        nwalkers = self.walkers_spin.value()
        nsteps = self.steps_spin.value()
        burnin = self.burnin_spin.value()

        self._fitting_worker = FittingWorker(
            composite, wave_use, flux_use, err_use,
            nwalkers=nwalkers, nsteps=nsteps, burnin=burnin,
        )
        self._fitting_worker.progress.connect(self._on_mcmc_progress)
        self._fitting_worker.finished.connect(self._on_mcmc_finished)
        self._fitting_worker.error.connect(self._on_mcmc_error)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.fit_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage('MCMC fitting in progress...')

        self._fitting_worker.start()

    def _stop_mcmc(self):
        if self._fitting_worker is not None:
            self._fitting_worker.cancel()
            self._fitting_worker.wait(3000)
            self._fitting_worker = None
        self.stop_btn.setEnabled(False)
        self._update_fit_button()
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage('MCMC fitting stopped.')

    def _on_mcmc_progress(self, pct):
        self.progress_bar.setValue(pct)
        self.statusBar().showMessage(f'MCMC fitting: {pct}%')

    def _on_mcmc_finished(self, flat_samples, param_names, model):
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self._update_fit_button()

        self._last_samples = flat_samples
        self._last_param_names = param_names
        self.corner_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        for comp in self._components:
            if not comp['visible']:
                continue
            for pname in comp['model'].param_names:
                p = getattr(comp['model'], pname)
                if not p.fixed and not p.tied:
                    idx = self._components.index(comp)
                    self.param_panel.update_param_value(idx, pname, p.value)

        wave = self._get_wave_for_eval()
        if wave is not None:
            lower, upper, best = compute_confidence_band(
                model, wave, flat_samples, param_names,
            )
            if lower is not None:
                self.canvas.clear_confidence_band()
                self.canvas.show_confidence_band(wave, lower, upper)

        self._update_canvas()

        chi2_r, bic, n_data, n_params = self._compute_fit_stats(model)
        self._last_chi2_r = chi2_r
        self._last_bic = bic

        self.statusBar().showMessage(
            f'MCMC fitting complete. χ²_r = {chi2_r:.2f}, BIC = {bic:.1f}'
        )

    def _on_mcmc_error(self, msg):
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self._update_fit_button()
        QMessageBox.warning(self, 'MCMC Error', msg)
        self.statusBar().showMessage(f'MCMC error: {msg}')

    def _show_corner(self):
        if self._last_samples is None or self._last_param_names is None:
            QMessageBox.information(self, 'Info', 'Run MCMC first to generate posterior samples.')
            return

        dialog = CornerPlotDialog(self._last_samples, self._last_param_names, self)
        dialog.exec_()

    def _save_results(self):
        if self._last_samples is None or self._last_param_names is None:
            QMessageBox.information(self, 'Info', 'Run MCMC first to generate posterior samples.')
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, 'Save Fitting Results', 'fit_results',
            'JSON files (*.json);;Pickle files (*.pkl);;All files (*)',
        )
        if not filepath:
            return

        flat_samples = self._last_samples
        param_names = self._last_param_names
        scale = self._flux_scale

        visible = [c for c in self._components if c['visible']]

        param_to_col = {}
        col_idx = 0
        for comp in visible:
            for pname in comp['model'].param_names:
                p = getattr(comp['model'], pname)
                if not p.fixed and not p.tied:
                    if col_idx < len(param_names):
                        param_to_col[id(p)] = col_idx
                        col_idx += 1

        xmin, xmax = self.canvas.ax.get_xlim()
        results = {
            'flux_unit': 'erg/s/cm^2/A',
            'flux_scale': float(scale),
            'redshift': float(self._z),
            'in_rest_frame': bool(self._in_rest_frame),
            'fit_wavelength_range': [float(xmin), float(xmax)],
            'reduced_chi2': float(self._last_chi2_r) if self._last_chi2_r is not None else None,
            'bic': float(self._last_bic) if self._last_bic is not None else None,
            'components': [],
        }
        for comp in visible:
            info = MODELS.get(comp['model_name'])
            comp_idx = self._components.index(comp)
            comp_dict = {
                'name': comp['name'],
                'model_name': comp['model_name'],
                'parameters': {},
            }
            if info is not None and info['category'] == 'absorption':
                comp_dict['absorbs'] = sorted(comp.get('absorbs', set()))
            for pname in comp['model'].param_names:
                p = getattr(comp['model'], pname)
                sf = scale if self._param_needs_scale(pname) else 1.0
                entry = {
                    'value': float(p.value) * sf,
                    'fixed': bool(p.fixed),
                }
                if id(p) in param_to_col:
                    col = flat_samples[:, param_to_col[id(p)]]
                    p16, p50, p84 = np.percentile(col, [16, 50, 84])
                    entry['median'] = float(p50) * sf
                    entry['p16'] = float(p16) * sf
                    entry['p84'] = float(p84) * sf
                    entry['uncertainty_lo'] = float(p50 - p16) * sf
                    entry['uncertainty_hi'] = float(p84 - p50) * sf
                lb, ub = p.bounds
                entry['bounds'] = [float(lb) * sf if lb is not None else None,
                                   float(ub) * sf if ub is not None else None]
                comp_dict['parameters'][pname] = entry
            results['components'].append(comp_dict)

        if filepath.endswith('.pkl'):
            with open(filepath, 'wb') as f:
                pickle.dump(results, f)
        else:
            if not filepath.endswith('.json'):
                filepath += '.json'
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)

        self.statusBar().showMessage(f'Results saved to {filepath}')

    def _load_results(self):
        if self.spectrum is None:
            QMessageBox.warning(self, 'Warning', 'Open a spectrum first.')
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, 'Load Fitting Results', '',
            'JSON files (*.json);;Pickle files (*.pkl);;All files (*)',
        )
        if not filepath:
            return

        try:
            if filepath.endswith('.pkl'):
                with open(filepath, 'rb') as f:
                    results = pickle.load(f)
            else:
                with open(filepath) as f:
                    results = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load results:\n{e}')
            return

        comps_data = results.get('components', [])
        if not comps_data:
            QMessageBox.warning(self, 'Warning', 'No components found in file.')
            return

        file_scale = results.get('flux_scale', 1.0)

        if 'redshift' in results:
            saved_z = results['redshift']
            saved_rest = results.get('in_rest_frame', saved_z > 0)
            self.z_edit.setText(f'{saved_z}')
            if saved_z > 0 and saved_rest:
                self._apply_redshift()
            elif self._in_rest_frame and not saved_rest:
                self._to_observed_frame()

        if 'fit_wavelength_range' in results:
            saved_range = results['fit_wavelength_range']
            self.wave_min_edit.setText(f'{saved_range[0]:.2f}')
            self.wave_max_edit.setText(f'{saved_range[1]:.2f}')
            self.canvas.ax.set_xlim(saved_range[0], saved_range[1])
            self._auto_fit_range()

        while self._components:
            self._remove_component(0)

        for cd in comps_data:
            model_name = cd.get('model_name')
            if model_name not in MODELS:
                QMessageBox.warning(self, 'Warning', f'Unknown model: {model_name}')
                continue

            params = cd.get('parameters', {})
            wavec_val = 0.0
            if 'wavec' in params:
                wavec_val = params['wavec']['value']

            wave = self.spectrum['wave']
            if wavec_val == 0.0:
                wavec_val = float(np.mean(wave))

            wave_range = self.canvas.get_visible_range()
            model = create_model(model_name, wavec=wavec_val, wave_range=wave_range)

            idx = self._component_counter
            self._component_counter += 1

            info = MODELS[model_name]
            display = f'{model_name} #{idx}'
            if info['has_wavec'] and wavec_val:
                display = f'{model_name} ({wavec_val:.1f})'

            color = COMPONENT_COLORS[len(self._components) % len(COMPONENT_COLORS)]

            comp = {
                'id': idx,
                'name': display,
                'model_name': model_name,
                'model': model,
                'visible': True,
                'color': color,
            }

            if info['category'] == 'absorption':
                comp['absorbs'] = set(cd.get('absorbs', []))

            self._components.append(comp)

            panel_idx = len(self._components) - 1
            self.param_panel.add_component(panel_idx, comp, self._components)

            for pname in model.param_names:
                if pname in params:
                    p = getattr(model, pname)
                    val_phys = params[pname]['value']
                    if self._param_needs_scale(pname):
                        val_scaled = val_phys / self._flux_scale
                    else:
                        val_scaled = val_phys
                    p.value = val_scaled
                    self.param_panel.update_param_value(panel_idx, pname, val_scaled)

                    if params[pname].get('fixed', False):
                        p.fixed = True

        self._refresh_absorption_panels()
        self._update_drag_components()
        self._update_canvas()
        self._update_fit_button()

        if 'reduced_chi2' in results and 'bic' in results:
            chi2_r = results['reduced_chi2']
            bic = results['bic']
            if chi2_r is not None and bic is not None:
                self._last_chi2_r = chi2_r
                self._last_bic = bic
                self.canvas.show_stats(chi2_r, bic)

        self.statusBar().showMessage(f'Loaded results from {filepath}')

    @staticmethod
    def _param_needs_scale(param_name):
        return param_name in ('amplitude', 'scale', 'i_ref')

    @staticmethod
    def _compute_flux_scale(flux):
        valid = np.abs(flux[np.isfinite(flux)])
        if len(valid) == 0 or np.median(valid) == 0:
            return 1.0, 0
        median = float(np.median(valid))
        exp = int(np.floor(np.log10(median)))
        scale = 10.0 ** exp
        return scale, exp

    def _update_ylabel(self):
        exp = self._flux_scale_exp
        self.canvas.ax.set_ylabel(
            f'Flux (×10$^{{{exp}}}$ erg s$^{{-1}}$ cm$^{{-2}}$ Å$^{{-1}}$)',
            fontsize=11,
        )
        self.canvas.ax_res.set_ylabel('Residual', fontsize=10)
        self.canvas.canvas.draw_idle()

    def _reset_zoom(self):
        if self.spectrum is not None:
            wave = self.spectrum['wave']
            margin = (wave[-1] - wave[0]) * 0.02
            self.canvas.ax.set_xlim(wave[0] - margin, wave[-1] + margin)
            self.canvas.canvas.draw_idle()
            self._sync_range_fields()

    def _set_display_range(self):
        xmin = self._parse_float(self.wave_min_edit.text())
        xmax = self._parse_float(self.wave_max_edit.text())
        ymin = self._parse_float(self.y_min_edit.text())
        ymax = self._parse_float(self.y_max_edit.text())

        if xmin is not None and xmax is not None and xmin < xmax:
            self.canvas.ax.set_xlim(xmin, xmax)
        if ymin is not None and ymax is not None and ymin < ymax:
            self.canvas.ax.set_ylim(ymin, ymax)

        rymin = self._parse_float(self.res_y_min_edit.text())
        rymax = self._parse_float(self.res_y_max_edit.text())
        if rymin is not None and rymax is not None and rymin < rymax:
            self.canvas.set_residual_ylim(rymin, rymax)

        self.canvas.canvas.draw_idle()

    def _auto_fit_range(self):
        if self.spectrum is None:
            return
        wave = self.spectrum['wave']
        flux = self.spectrum['flux']

        xmin, xmax = self.canvas.ax.get_xlim()
        mask = (wave >= xmin) & (wave <= xmax) & np.isfinite(flux)
        if np.any(mask):
            f = flux[mask]
            ymin, ymax = np.nanmin(f), np.nanmax(f)
            margin = (ymax - ymin) * 0.05
            if margin == 0:
                margin = abs(ymax) * 0.1 + 1e-10
            self.canvas.ax.set_ylim(ymin - margin, ymax + margin)

        self.canvas.canvas.draw_idle()
        self._sync_range_fields()

    def _range_from_zoom(self):
        self._sync_range_fields()

    def _sync_range_fields(self):
        xmin, xmax = self.canvas.ax.get_xlim()
        ymin, ymax = self.canvas.ax.get_ylim()
        self.wave_min_edit.setText(f'{xmin:.2f}')
        self.wave_max_edit.setText(f'{xmax:.2f}')
        self.y_min_edit.setText(f'{ymin:.6g}')
        self.y_max_edit.setText(f'{ymax:.6g}')

    @staticmethod
    def _parse_float(text):
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    def _apply_redshift(self):
        if self._observed_spectrum is None:
            QMessageBox.warning(self, 'Warning', 'Open a spectrum first.')
            return
        z = self._parse_float(self.z_edit.text())
        if z is None or z < 0:
            QMessageBox.warning(self, 'Warning', 'Enter a valid redshift (z >= 0).')
            return

        self._z = z
        obs = self._observed_spectrum
        wave_obs = obs['wave']
        flux_phys = obs['flux']
        err_phys = obs['err']

        wave_rest = wave_obs / (1.0 + z)
        flux_rest = flux_phys * (1.0 + z)
        err_rest = err_phys * (1.0 + z)

        self._flux_scale, self._flux_scale_exp = self._compute_flux_scale(flux_rest)

        self.spectrum = {
            'wave': wave_rest,
            'flux': flux_rest / self._flux_scale,
            'err': err_rest / self._flux_scale,
        }
        self._in_rest_frame = True

        self.canvas.clear_all()
        self.canvas.plot_spectrum(
            self.spectrum['wave'], self.spectrum['flux'], self.spectrum['err'],
        )
        self._update_canvas()
        self._auto_fit_range()
        self._update_xlabel()
        self._update_ylabel()

        self.statusBar().showMessage(
            f'Rest frame (z={z:.4f}): {len(self.spectrum["wave"])} points | '
            f'wave: {self.spectrum["wave"][0]:.1f}–{self.spectrum["wave"][-1]:.1f} Å'
        )

    def _to_observed_frame(self):
        if self._observed_spectrum is None:
            return
        obs = self._observed_spectrum

        self._flux_scale, self._flux_scale_exp = self._compute_flux_scale(obs['flux'])

        self.spectrum = {
            'wave': obs['wave'].copy(),
            'flux': obs['flux'] / self._flux_scale,
            'err': obs['err'] / self._flux_scale,
        }
        self._in_rest_frame = False
        self._z = 0.0
        self.z_edit.setText('0')

        self.canvas.clear_all()
        self.canvas.plot_spectrum(
            self.spectrum['wave'], self.spectrum['flux'], self.spectrum['err'],
        )
        self._update_canvas()
        self._auto_fit_range()
        self._update_xlabel()
        self._update_ylabel()

        self.statusBar().showMessage('Switched back to observed frame.')

    def _update_xlabel(self):
        if self._in_rest_frame:
            self.canvas.ax_res.set_xlabel('Rest-frame Wavelength (Å)', fontsize=12)
        else:
            self.canvas.ax_res.set_xlabel('Wavelength (Å)', fontsize=12)
        self.canvas.canvas.draw_idle()
