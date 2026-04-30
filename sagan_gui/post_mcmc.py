"""Post-MCMC visualization: confidence bands and corner plot."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtWidgets import QDialog, QVBoxLayout


def compute_confidence_band(model, wave, flat_samples, param_names,
                            n_samples=200, percentile=16):
    """Compute confidence band from MCMC samples.

    Returns (lower, upper, best_fit_flux).
    """
    n_total = len(flat_samples)
    indices = np.random.choice(n_total, size=min(n_samples, n_total), replace=False)
    selected = flat_samples[indices]

    fluxes = []
    original_values = {pn: getattr(model, pn).value for pn in param_names}

    for row in selected:
        for j, pn in enumerate(param_names):
            setattr(model, pn, row[j])
        for pn in model.param_names:
            p = getattr(model, pn)
            if p.tied:
                p.value = p.tied(model)
        try:
            f = model(wave)
            fluxes.append(f)
        except Exception:
            pass

    for pn, val in original_values.items():
        setattr(model, pn, val)

    if len(fluxes) == 0:
        return None, None, None

    fluxes = np.array(fluxes)
    lower = np.percentile(fluxes, percentile, axis=0)
    upper = np.percentile(fluxes, 100 - percentile, axis=0)
    best_fit = np.median(fluxes, axis=0)

    return lower, upper, best_fit


class CornerPlotDialog(QDialog):
    """Display a corner plot of MCMC posterior samples."""

    def __init__(self, flat_samples, param_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle('MCMC Posterior Distributions')
        self.setMinimumSize(600, 600)

        layout = QVBoxLayout(self)
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas)

        self._draw_corner(flat_samples, param_names)

    def _draw_corner(self, samples, param_names):
        ndim = len(param_names)
        fig = self.fig
        fig.clear()

        axes = fig.subplots(ndim, ndim)
        if ndim == 1:
            axes = np.array([[axes]])

        for i in range(ndim):
            for j in range(ndim):
                ax = axes[i][j] if ndim > 1 else axes[0][0]
                if j > i:
                    ax.set_visible(False)
                    continue

                if i == j:
                    ax.hist(samples[:, i], bins=50, density=True,
                            color='#1f77b4', alpha=0.7, edgecolor='none')
                    ax.axvline(np.median(samples[:, i]), color='red', linewidth=1.5)
                else:
                    ax.hist2d(samples[:, j], samples[:, i], bins=50,
                              cmap='Blues', density=True)
                    ax.axvline(np.median(samples[:, j]), color='red',
                               linewidth=0.8, alpha=0.7)
                    ax.axhline(np.median(samples[:, i]), color='red',
                               linewidth=0.8, alpha=0.7)

                if i == ndim - 1:
                    ax.set_xlabel(param_names[j], fontsize=8)
                else:
                    ax.set_xticklabels([])

                if j == 0 and i > 0:
                    ax.set_ylabel(param_names[i], fontsize=8)
                else:
                    ax.set_yticklabels([])

                ax.tick_params(labelsize=7)

        fig.subplots_adjust(hspace=0.05, wspace=0.05, left=0.15, right=0.95,
                            top=0.95, bottom=0.08)
        self.canvas.draw()
