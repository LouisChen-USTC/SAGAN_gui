"""Matplotlib canvas for spectrum display."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from .model_registry import MODELS, COMPONENT_COLORS
from .drag_handler import _get_line_anchors


class SpectrumCanvas(QWidget):
    """Widget containing the matplotlib spectrum plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.08)
        self.ax = self.fig.add_subplot(self.gs[0])
        self.ax_res = self.fig.add_subplot(self.gs[1], sharex=self.ax)
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.08)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._data_lines = None
        self._component_lines = {}
        self._anchor_artists = {}
        self._composite_line = None
        self._confidence_fill = None
        self._residual_line = None
        self._residual_zero_line = None
        self._residual_err_container = None

        self._spectrum = None
        self._components = []

        self._init_axes()

    def _init_axes(self):
        self.ax.set_ylabel('Flux', fontsize=12)
        self.ax.tick_params(labelsize=10, labelbottom=False)
        self.ax_res.set_xlabel('Wavelength (Å)', fontsize=12)
        self.ax_res.set_ylabel('Residual', fontsize=10)
        self.ax_res.tick_params(labelsize=9)
        self.ax_res.axhline(0, color='gray', linewidth=0.5, linestyle='--')
        self.ax_res.set_ylim(-10, 10)

    def set_residual_ylim(self, ymin, ymax):
        self.ax_res.set_ylim(ymin, ymax)
        self.canvas.draw_idle()

    def plot_spectrum(self, wave, flux, err=None):
        """Plot the observed spectrum data as step histogram with error bars."""
        self._spectrum = (wave, flux, err)
        self.ax.clear()
        self.ax_res.clear()

        self.ax.step(
            wave, flux, where='mid', color='black',
            linewidth=0.8, alpha=0.8, label='Data', zorder=1,
        )

        if err is not None and np.any(err > 0):
            self.ax.errorbar(
                wave, flux, yerr=err,
                fmt='none', ecolor='gray', elinewidth=0.5,
                capsize=1.5, alpha=0.5, zorder=2,
            )

        self.ax.set_ylabel('Flux', fontsize=12)
        self.ax.tick_params(labelsize=10, labelbottom=False)
        self.ax.legend(loc='upper right', fontsize=9)
        self._component_lines = {}
        self._anchor_artists = {}
        self._composite_line = None
        self._confidence_fill = None
        self._residual_line = None
        self._residual_zero_line = None
        self._residual_err_container = None
        self._stats_text = None

        self.ax_res.axhline(0, color='gray', linewidth=0.5, linestyle='--')
        self.ax_res.set_xlabel('Wavelength (Å)', fontsize=12)
        self.ax_res.set_ylabel('Residual', fontsize=10)
        self.ax_res.tick_params(labelsize=9)
        self.ax_res.set_ylim(-10, 10)
        self.canvas.draw()

    def _remove_anchors(self, index):
        if index in self._anchor_artists:
            for artist in self._anchor_artists[index]:
                artist.remove()
            del self._anchor_artists[index]

    def _draw_anchors(self, index, comp):
        self._remove_anchors(index)

        model_name = comp['model_name']
        info = MODELS.get(model_name)
        if info is None or info['category'] != 'line':
            return

        anchors = _get_line_anchors(comp['model'], model_name)
        if anchors is None:
            return

        artists = []
        for ax_x, ax_y, role in anchors:
            marker_size = 9 if role == 'peak' else 7
            line, = self.ax.plot(
                ax_x, ax_y, 'o', color='#2ecc71', markersize=marker_size,
                markeredgecolor='white', markeredgewidth=1.2, zorder=10,
            )
            artists.append(line)
        self._anchor_artists[index] = artists

    def _compute_composite(self, wave):
        additive = []
        absorptions = []

        for i, comp in enumerate(self._components):
            if not comp['visible']:
                continue
            info = MODELS.get(comp['model_name'])
            if info is not None and info['category'] == 'absorption':
                absorptions.append((i, comp))
            else:
                additive.append((i, comp))

        if not additive:
            return np.zeros_like(wave, dtype=float)

        if not absorptions:
            result = np.zeros_like(wave, dtype=float)
            for _, comp in additive:
                try:
                    result += comp['model'](wave)
                except Exception:
                    continue
            return result

        groups = {}
        for add_i, add_comp in additive:
            key = frozenset(
                abs_i for abs_i, abs_comp in absorptions
                if abs_comp.get('absorbs') is None or add_i in abs_comp['absorbs']
            )
            groups.setdefault(key, []).append(add_comp)

        result = np.zeros_like(wave, dtype=float)
        for abs_key, group_comps in groups.items():
            group_sum = np.zeros_like(wave, dtype=float)
            for comp in group_comps:
                try:
                    group_sum += comp['model'](wave)
                except Exception:
                    continue
            for abs_i in sorted(abs_key):
                try:
                    group_sum *= self._components[abs_i]['model'](wave)
                except Exception:
                    continue
            result += group_sum

        return result

    def _update_residual(self, wave):
        if self._spectrum is None:
            return
        flux = self._spectrum[1]
        err = self._spectrum[2]
        composite = self._compute_composite(wave)
        residual = flux - composite

        if self._residual_line is not None:
            self._residual_line.set_ydata(residual)
        else:
            self._residual_line, = self.ax_res.step(
                wave, residual, where='mid', color='black',
                linewidth=0.6, alpha=0.7, zorder=1,
            )

        if self._residual_err_container is not None:
            self._residual_err_container.remove()
        self._residual_err_container = None
        self._stats_text = None

        if err is not None and np.any(err > 0):
            self._residual_err_container = self.ax_res.fill_between(
                wave, residual - err, residual + err,
                color='gray', alpha=0.25, zorder=0,
            )

    def plot_components(self, components, wave):
        self._components = components

        stale_keys = set(self._component_lines.keys()) - set(range(len(components)))
        for key in stale_keys:
            self._component_lines.pop(key).remove()
            self._remove_anchors(key)

        for i, comp in enumerate(components):
            if not comp['visible']:
                if i in self._component_lines:
                    self._component_lines[i].set_visible(False)
                self._remove_anchors(i)
                continue

            info = MODELS.get(comp['model_name'])
            is_absorption = info is not None and info['category'] == 'absorption'

            if is_absorption:
                if i in self._component_lines:
                    self._component_lines[i].set_visible(False)
                self._remove_anchors(i)
                continue

            try:
                model_flux = comp['model'](wave)
            except Exception:
                model_flux = np.zeros_like(wave)

            color = COMPONENT_COLORS[i % len(COMPONENT_COLORS)]

            if i in self._component_lines:
                line = self._component_lines[i]
                line.set_ydata(model_flux)
                line.set_visible(True)
            else:
                line, = self.ax.plot(
                    wave, model_flux, '-', color=color, linewidth=1.2,
                    alpha=0.7, label=comp['name'], zorder=3,
                )
                self._component_lines[i] = line

            self._draw_anchors(i, comp)

        composite_flux = self._compute_composite(wave)

        if self._composite_line is not None:
            self._composite_line.set_ydata(composite_flux)
        else:
            self._composite_line, = self.ax.plot(
                wave, composite_flux, '-', color='red', linewidth=2.0,
                label='Composite', zorder=5,
            )

        self._update_residual(wave)

        self.ax.legend(loc='upper right', fontsize=9)
        self.canvas.draw_idle()

    def update_single_component(self, index, comp, wave):
        info = MODELS.get(comp['model_name'])
        is_absorption = info is not None and info['category'] == 'absorption'

        if not is_absorption:
            if index in self._component_lines:
                if comp['visible']:
                    try:
                        model_flux = comp['model'](wave)
                    except Exception:
                        model_flux = np.zeros_like(wave)
                    self._component_lines[index].set_ydata(model_flux)
                    self._component_lines[index].set_visible(True)
                    self._draw_anchors(index, comp)
                else:
                    self._component_lines[index].set_visible(False)
                    self._remove_anchors(index)

        composite_flux = self._compute_composite(wave)

        if self._composite_line is not None:
            self._composite_line.set_ydata(composite_flux)

        self._update_residual(wave)
        self.canvas.draw_idle()

    def show_confidence_band(self, wave, lower, upper):
        if self._confidence_fill is not None:
            self._confidence_fill.remove()

        self._confidence_fill = self.ax.fill_between(
            wave, lower, upper, color='red', alpha=0.2, zorder=4,
            label='68% confidence',
        )
        self.ax.legend(loc='upper right', fontsize=9)
        self.canvas.draw_idle()

    def clear_confidence_band(self):
        if self._confidence_fill is not None:
            self._confidence_fill.remove()
            self._confidence_fill = None
            self.canvas.draw_idle()

    def get_visible_range(self):
        return tuple(self.ax.get_xlim())

    def get_wave_in_range(self, wave):
        xmin, xmax = self.get_visible_range()
        mask = (wave >= xmin) & (wave <= xmax)
        return wave[mask]

    def clear_all(self):
        self.ax.clear()
        self.ax_res.clear()
        self._data_lines = None
        self._component_lines = {}
        self._anchor_artists = {}
        self._composite_line = None
        self._confidence_fill = None
        self._residual_line = None
        self._residual_err_container = None
        self._stats_text = None
        self._spectrum = None
        self._components = []
        self._init_axes()

    def show_stats(self, chi2_r, bic):
        if self._stats_text is not None:
            self._stats_text.remove()
            self._stats_text = None
        text = f'χ²_r = {chi2_r:12.2f}\nBIC   = {bic:12.1f}'
        self._stats_text = self.ax.text(
            0.02, 0.98, text,
            transform=self.ax.transAxes,
            fontfamily='monospace',
            fontsize=9, verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='none'),
            zorder=20,
        )
        self.canvas.draw_idle()

    def clear_stats(self):
        if self._stats_text is not None:
            self._stats_text.remove()
            self._stats_text = None
            self.canvas.draw_idle()
