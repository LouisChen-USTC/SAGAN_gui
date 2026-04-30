"""Registry of supported SAGAN models with GUI metadata."""
from collections import OrderedDict
import numpy as np

from sagan.constants import ls_km
from sagan import (Line_Gaussian, Line_Exponential, Line_Absorption,
                   Line_Absorption_log_tau, WindowedPowerLaw1D, BlackBody,
                   BalmerPseudoContinuum, IronTemplate)

MODELS = OrderedDict([
    ('Gaussian Line', {
        'class': Line_Gaussian,
        'category': 'line',
        'has_wavec': True,
    }),
    ('Exponential Line', {
        'class': Line_Exponential,
        'category': 'line',
        'has_wavec': True,
    }),
    ('Absorption Line', {
        'class': Line_Absorption,
        'category': 'absorption',
        'has_wavec': True,
    }),
    ('Absorption Line (log tau)', {
        'class': Line_Absorption_log_tau,
        'category': 'absorption',
        'has_wavec': True,
    }),
    ('Power Law', {
        'class': WindowedPowerLaw1D,
        'category': 'continuum',
        'has_wavec': False,
    }),
    ('Black Body', {
        'class': BlackBody,
        'category': 'continuum',
        'has_wavec': False,
    }),
    ('Balmer Continuum', {
        'class': BalmerPseudoContinuum,
        'category': 'continuum',
        'has_wavec': False,
    }),
    ('Iron Template (Park 2022)', {
        'class': IronTemplate,
        'category': 'template',
        'has_wavec': False,
        'constructor_kwargs': {'template_name': 'park2022'},
    }),
    ('Iron Template (Boroson 1992)', {
        'class': IronTemplate,
        'category': 'template',
        'has_wavec': False,
        'constructor_kwargs': {'template_name': 'boroson1992'},
    }),
])

LINE_PRESETS = OrderedDict([
    ('Custom', None),
    (r'Hα 6564.6', 6564.61),
    (r'Hβ 4862.7', 4862.68),
    (r'Hγ 4341.7', 4341.68),
    (r'Hδ 4102.9', 4102.89),
    (r'[O III] 5007', 5008.239),
    (r'[O III] 4959', 4960.295),
    (r'[N II] 6583', 6585.27),
    (r'[N II] 6548', 6549.86),
    (r'[S II] 6718', 6718.29),
    (r'[S II] 6733', 6732.67),
    (r'[O II] 3727', 3726.032),
    (r'[O II] 3729', 3728.815),
    (r'He II 4686', 4686.0),
    (r'Mg II 2799', 2799.12),
    (r'C IV 1548', 1548.2),
    (r'Lyα 1216', 1215.67),
])

COMPONENT_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]


def create_model(model_name, wavec=None, wave_range=None):
    """Create a SAGAN model instance with sensible defaults.

    Parameters
    ----------
    model_name : str
        Key from MODELS registry.
    wavec : float or None
        Central wavelength for line profiles.
    wave_range : (float, float) or None
        Wavelength range for continuum windowing.

    Returns
    -------
    model : Fittable1DModel instance
    """
    info = MODELS[model_name]
    cls = info['class']
    kwargs = dict(info.get('constructor_kwargs', {}))

    if wavec is not None and info['has_wavec']:
        kwargs['wavec'] = wavec

    model = cls(**kwargs)

    if model_name == 'Power Law' and wave_range is not None:
        model.x_min = wave_range[0]
        model.x_max = wave_range[1]
        model.x_0 = np.mean(wave_range)

    return model


def get_peak_position(model, model_name):
    """Return (x_peak, y_peak) for a model, or None if not applicable."""
    info = MODELS.get(model_name)
    if info is None:
        return None

    category = info['category']
    if category not in ('line', 'absorption'):
        return None

    wavec = None
    dv = 0.0
    for pname in model.param_names:
        p = getattr(model, pname)
        if pname == 'wavec':
            wavec = p.value
        elif pname == 'dv':
            dv = p.value

    if wavec is None:
        return None

    peak_x = wavec * (1.0 + dv / ls_km)

    if category == 'line':
        for pname in model.param_names:
            if pname == 'amplitude':
                return (peak_x, getattr(model, pname).value)
    elif category == 'absorption':
        return (peak_x, None)

    return None


def get_param_role(model_name, param_name):
    """Return the role of a parameter: 'amplitude', 'dv', 'sigma', 'wavec', or None."""
    if param_name == 'wavec':
        return 'wavec'
    if param_name == 'dv':
        return 'dv'
    if param_name in ('amplitude', 'scale', 'i_ref'):
        return 'amplitude'
    if param_name in ('sigma', 'w', 'stddev'):
        return 'sigma'
    if param_name in ('tau_0', 'log_tau0'):
        return 'amplitude'
    if param_name == 'Cf':
        return 'cf'
    if param_name == 'temperature':
        return 'temperature'
    if param_name in ('x_min', 'x_max', 'x_0'):
        return 'window'
    if param_name == 'alpha':
        return 'alpha'
    if param_name == 'z':
        return 'redshift'
    return None
