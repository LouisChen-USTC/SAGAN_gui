# SAGAN Project Notes

## Architecture

SAGAN ([https://github.com/jyshangguan/SAGAN](https://github.com/jyshangguan/SAGAN))
is a separate package. All spectral models subclass
`astropy.modeling.core.Fittable1DModel` with `Parameter` descriptors.

- `continuum.py` — power-law, blackbody, Balmer continuum models
- `line_profile.py` — Gaussian, exponential, P-Cygni, absorption, Hermite line profiles
- `convolution.py` — LSF convolution utilities
- `iron_template.py` — Fe II emission templates (Boroson 1992, Park 2022)
- `stellar_continuum.py` — stellar population and star templates
- `utils.py` — line wavelength dictionary, MCMC fitting helpers, spectrum I/O
- `plot.py` — fitting result visualization
- `constants.py` — speed of light constant
- `data/` — bundled template data (FITS, IPAC, .dat); loaded at import time

Entry point: `sagan/__init__.py` re-exports all public names via wildcard imports.

## Setup

Requires the SAGAN package to be installed and importable (`import sagan`).
The GUI no longer adds `SAGAN/` to `sys.path`.

Install GUI dependencies:
```bash
pip install -r requirements.txt
```

Dependencies: `sagan`, `astropy`, `numpy`, `scipy`, `matplotlib`, `spectres`,
`sfdmap2`, `PyAstronomy`, `emcee`, `PyQt5`.

`extinction` and `pcygni_profile` are optional in SAGAN (gracefully skipped).

## Gotchas

- **Hardcoded path**: `line_profile.py:26` contains
  `pcygni_temp_path = '/Users/changhaosmac/Documents/pcygni_profile_templates/'`.
  This must be updated for the local machine before using P-Cygni profiles.

- **Import-time I/O**: `iron_template.py` and `stellar_continuum.py` read data
  files from `sagan/data/` at import time. The `data/` directory must stay
  co-located with the package modules.

- **No tests or CI**: There are no automated tests, linter, or CI workflows.

- **`pcygni_profile` import**: Made optional in `line_profile.py` (try/except).
  If missing, P-Cygni classes will raise errors if used, but all other models work.

## SAGAN GUI

Interactive spectral fitting GUI at `sagan_gui/`.

### Run

```bash
pip install -r requirements.txt
python -m sagan_gui.run
```

### Supported models (v1)

Gaussian Line, Exponential Line, Absorption Line, Absorption Line (log τ),
Power Law, Black Body, Balmer Continuum, Iron Template (Park 2022 & Boroson 1992).

### Spectrum formats

Auto-detected on load:
- **JWST binary table**: BinTableHDU with `wave`/`flux`/`err` columns (micron → Å)
- **IRAF 1D image**: PrimaryHDU with WCS headers (`CRVAL1`/`CDELT1`/`CRPIX1`)
- **SDSS**: BinTableHDU with `loglam`/`flux`/`ivar` columns

### Architecture

- `main.py` — QMainWindow, orchestrates all components
- `canvas.py` — matplotlib FigureCanvasQTAgg with spectrum + model overlay
- `drag_handler.py` — mouse drag to adjust line peak amplitude/dv/sigma
- `param_panel.py` — per-component parameter editors (bidirectional with canvas)
- `spectrum_loader.py` — multi-format FITS loader with unit conversion
- `model_registry.py` — model metadata, creation, and line presets
- `fitting_worker.py` — QThread wrapping emcee MCMC with progress/cancel
- `post_mcmc.py` — confidence band computation + corner plot dialog

## Example

See `SAGAN/example/` for demo notebooks fitting spectra, or the SAGAN
documentation at https://jyshangguan.github.io/SAGAN/
