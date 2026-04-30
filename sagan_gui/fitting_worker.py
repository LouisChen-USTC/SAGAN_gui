"""MCMC fitting worker thread."""
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

import emcee


class FittingWorker(QThread):
    """Run MCMC fitting in a background thread."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(object, object, object)
    error = pyqtSignal(str)

    def __init__(self, model, wave, flux, err, nwalkers=50, nsteps=6000,
                 burnin=2000, parent=None):
        super().__init__(parent)
        self.model = model
        self.wave = wave
        self.flux = flux
        self.err = err
        self.nwalkers = nwalkers
        self.nsteps = nsteps
        self.burnin = burnin
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            param_names = []
            for pname in self.model.param_names:
                p = getattr(self.model, pname)
                if not p.fixed and not p.tied:
                    param_names.append(pname)

            if len(param_names) == 0:
                self.error.emit("No free parameters to fit.")
                return

            theta0 = np.array([getattr(self.model, pn).value for pn in param_names])
            ndim = len(theta0)

            for i, pn in enumerate(param_names):
                p = getattr(self.model, pn)
                lb, ub = p.bounds
                if lb is not None:
                    lb = float(lb)
                if ub is not None:
                    ub = float(ub)
                if lb is not None and theta0[i] < lb:
                    theta0[i] = lb + 1e-8
                if ub is not None and theta0[i] > ub:
                    theta0[i] = ub - 1e-8

            pos = theta0 + 1e-8 * np.random.randn(self.nwalkers, ndim)

            for i, pn in enumerate(param_names):
                p = getattr(self.model, pn)
                lb, ub = p.bounds
                if lb is not None:
                    pos[:, i] = np.maximum(pos[:, i], float(lb) + 1e-10)
                if ub is not None:
                    pos[:, i] = np.minimum(pos[:, i], float(ub) - 1e-10)

            def log_prior(theta):
                for j, pn in enumerate(param_names):
                    p = getattr(self.model, pn)
                    lb, ub = p.bounds
                    if lb is not None and theta[j] < lb:
                        return -np.inf
                    if ub is not None and theta[j] > ub:
                        return -np.inf
                return 0.0

            def log_likelihood(theta):
                for j, pn in enumerate(param_names):
                    setattr(self.model, pn, theta[j])
                for pn in self.model.param_names:
                    p = getattr(self.model, pn)
                    if p.tied:
                        p.value = p.tied(self.model)
                model_flux = self.model(self.wave)
                return -0.5 * np.sum(((self.flux - model_flux) / self.err) ** 2)

            def log_probability(theta):
                lp = log_prior(theta)
                if not np.isfinite(lp):
                    return -np.inf
                return lp + log_likelihood(theta)

            sampler = emcee.EnsembleSampler(self.nwalkers, ndim, log_probability)

            pos, _, _ = sampler.run_mcmc(pos, self.burnin, progress=False)
            sampler.reset()

            total = self.nsteps
            for i, result in enumerate(sampler.sample(pos, iterations=total)):
                if self._cancelled:
                    self.error.emit("MCMC fitting cancelled.")
                    return
                pct = int(100.0 * (i + 1) / total)
                self.progress.emit(pct)

            flat_samples = sampler.get_chain(flat=True)
            best_fit = np.median(flat_samples, axis=0)
            for j, pn in enumerate(param_names):
                setattr(self.model, pn, best_fit[j])

            self.finished.emit(flat_samples, param_names, self.model)

        except Exception as e:
            self.error.emit(str(e))
