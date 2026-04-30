# SAGAN GUI — Interactive Spectral Fitting

A PyQt5 graphical interface for fitting astrophysical spectra using the
[SAGAN](https://github.com/jyshangguan/SAGAN) spectral modeling library.
Build composite models from emission lines, absorption lines, continua,
and iron templates, then fit them to your data with emcee MCMC.

## Quick Start

Make sure the [SAGAN](https://github.com/jyshangguan/SAGAN) spectral modeling package
is installed and importable (`import sagan`). You can install it with:

```bash
git clone https://github.com/jyshangguan/SAGAN.git
cd SAGAN
pip install -e .
```

Then install the GUI dependencies and run:

```bash
pip install -r requirements.txt
python -m sagan_gui.run
```

## A Worked Example: JWST AGN at z = 6.69

The `gui_example/` folder contains everything you need to try the GUI:

| File | Description |
|------|-------------|
| `rubies-egs63-v4_g395m-f290lp_4233_49140.spec.fits` | JWST NIRSpec G395M spectrum of an AGN at z = 6.69, flux in μJy |
| `fit_results.json` | Saved best-fit results for the Hα + [N II] complex |

The spectrum covers **26 851 – 54 997 Å** (observed frame). At z = 6.69
the Hα 6564.6 Å line is redshifted to ~50 489 Å. The fit model consists
of a power-law continuum, three Gaussians (2 broad + 1 narrow Hα components
), and an absorption line.

### Step-by-step

1. **Open the spectrum.** `File → Open Spectrum` (or `Ctrl+O`), select the
   FITS file. The flux is automatically converted from μJy to
   erg s⁻¹ cm⁻² Å⁻¹ and scaled for display. The y-axis label shows the
   scale factor.

2. **Set the redshift.** Enter `6.69` in the **Redshift z** field and click
   **To Rest Frame**. The wavelength axis now shows rest-frame values and
   Hα appears near 6565 Å.

3. **Zoom to the emission line.** Use the matplotlib toolbar (zoom rectangle)
   to zoom into ~6200 – 7000 Å, then click **From Zoom** to populate the
   display range fields. Click **Auto Fit** to adjust the y-axis.

4. **Add a power-law continuum.** Select `Power Law` from the model dropdown
   and click **+ Add**. In the parameter panel, expand `amplitude` (click ▸),
   adjust the value until the continuum level roughly matches the data.
   Set `x_min` and `x_max` to bracket the fitting window (e.g. 6300 – 6800 Å).

5. **Add emission lines.** Select `Gaussian Line`, pick `Hα 6564.6` from the
   preset dropdown, and click **+ Add**. Repeat to add additional Gaussians
   for the narrow and broad components. Drag the green anchor points on the
   plot to adjust amplitude, sigma, and velocity offset interactively.

6. **Add an absorption line.** Select `Absorption Line`, pick `Hα 6564.6`,
   and click **+ Add**. By default it absorbs all non-absorption components.
   The component panel shows a checklist — uncheck any component that should
   *not* be absorbed (e.g. if you want only the continuum absorbed but not
   a narrow line).

7. **Set parameter bounds.** For each parameter, click ▸ to expand the
   controls. Set **Lo** / **Hi** bounds and click **Set**. Check **Fixed**
   to freeze a parameter during MCMC (e.g. fix `wavec` to the laboratory
   wavelength).

8. **Run MCMC.** Set walkers, steps, and burn-in in the **MCMC Fitting**
   panel. Click **Run MCMC**. A progress bar tracks the fit. When done,
   the best-fit model and 68% confidence band are drawn on the plot, the
   residual panel updates, and the reduced χ² and BIC are shown in the
   upper-left corner.

9. **Inspect results.** Click **Corner Plot** to view the posterior
   distributions and parameter correlations.

10. **Save results.** Click **Save Results** to write a JSON (or pickle)
    file with best-fit values and uncertainties (16th, 50th, 84th
    percentiles) in physical units (erg s⁻¹ cm⁻² Å⁻¹).

11. **Reload results later.** Open the same spectrum, then click
    **Load Results** and select a previously saved JSON/pickle file. All
    components and parameters are restored automatically.

To see the example fit immediately, open the spectrum, set z = 6.69, go to
rest frame, then click **Load Results** and select `fit_results.json`.

## Supported Models

| Model | Category | Description |
|-------|----------|-------------|
| Gaussian Line | line | Gaussian emission line profile |
| Exponential Line | line | Exponential (Lorentzian-like) emission profile |
| Absorption Line | absorption | Optical-depth absorption with covering fraction |
| Absorption Line (log τ) | absorption | Same, with log-scaled optical depth |
| Power Law | continuum | Windowed power-law (F ∝ λ^α) |
| Black Body | continuum | Planck blackbody spectrum |
| Balmer Continuum | continuum | Balmer pseudo-continuum model |
| Iron Template (Park 2022) | template | Fe II UV/optical template |
| Iron Template (Boroson 1992) | template | Fe II optical template |

### Line Presets

When adding a line or absorption model, use the preset dropdown to
automatically set the central wavelength:

Hα, Hβ, Hγ, Hδ, [O III] 5007/4959, [N II] 6583/6548, [S II] 6718/6733,
[O II] 3727/3729, He II 4686, Mg II 2799, C IV 1548, Lyα 1216, or Custom.

## Spectrum Formats

The loader auto-detects the format on open:

| Format | Detection | Units |
|--------|-----------|-------|
| **JWST NIRSpec** | BinTableHDU with `wave`/`flux`/`err` columns | μm → Å, μJy |
| **IRAF 1D** | PrimaryHDU with WCS headers | Å |
| **SDSS** | BinTableHDU with `loglam`/`flux`/`ivar` columns | 10⁻¹⁷ erg/s/cm²/Å |

All spectra are converted to **erg s⁻¹ cm⁻² Å⁻¹** on load (JWST assumes
input in μJy) and auto-scaled for display.

## Composite Model

The total model is:

```
composite = Σᵢ [ Fᵢ(λ) × Πⱼ Aⱼ(λ) ]  +  Σₖ Fₖ(λ)
```

where the first sum is over additive components (lines, continua, templates)
that are absorbed, and the second sum is over additive components that are
*not* targeted by any absorption. `Aⱼ(λ)` are absorption models selected
per-component via the checklist in the absorption panel.

For example, if only Gaussian 1 and 2 are checked in the absorption
selector:

```
composite = (Gaussian₁ + Gaussian₂) × Absorption  +  Gaussian₃
```

This ensures each absorption model's parameters (τ₀, σ, Cf) appear only
*once* in the MCMC compound model.

## Interactive Controls

### Mouse Drag

For emission and absorption line models, green anchor points appear on the
plot:

| Anchor | Action |
|--------|--------|
| Peak (center) | Drag vertically to adjust **amplitude** |
| Sigma (sides) | Drag horizontally to adjust **sigma** (velocity width) |
| Line body | Drag horizontally to shift **dv** (velocity offset) |

A crosshair cursor appears when hovering over a draggable region. Dragging
only works when the matplotlib toolbar is in the default (arrow) mode.

### Parameter Panel

Each parameter row has a **▸** toggle that expands to reveal:

- **Lo / Hi** — lower and upper bounds for MCMC
- **Set** — apply the bounds
- **Fixed** — freeze the parameter during MCMC

Fixed parameters are highlighted with a yellow background.

### Display Range

- **λ min / λ max** — set the wavelength axis range
- **Y min / Y max** — set the flux axis range
- **Res Y min / Res Y max** — set the residual axis range (default: −10 to 10)
- **Set Range** — apply all range values
- **Auto Fit** — auto-scale y-axis to the visible data
- **From Zoom** — populate fields from the current zoom level

### Redshift

- **To Rest Frame** — divide wavelengths by (1+z), multiply flux by (1+z)
- **To Observed** — revert to original observed-frame data
- The display scale factor is recomputed on frame change

## MCMC Fitting

The GUI uses [emcee](https://emcee.readthedocs.io/) (affine-invariant
ensemble sampler) with a burn-in phase followed by production sampling.
The likelihood is Gaussian:

```
log L = −½ Σ (F_data − F_model)² / σ²
```

Uniform priors are set from the parameter bounds.

### Settings

| Field | Default | Description |
|-------|---------|-------------|
| Walkers | 50 | Number of ensemble walkers |
| Steps | 6000 | Production steps per walker |
| Burn-in | 2000 | Burn-in steps (discarded) |

Click **Stop** to cancel a running fit.

## Saving and Loading Results

### Save Results

Click **Save Results** after MCMC completes. The output is a JSON file
containing:

```json
{
  "flux_unit": "erg/s/cm^2/A",
  "flux_scale": 1e-19,
  "components": [
    {
      "name": "Gaussian Line (6564.6)",
      "model_name": "Gaussian Line",
      "parameters": {
        "amplitude": {
          "value": 5.48e-19,
          "fixed": false,
          "median": 5.48e-19,
          "p16": 4.44e-19,
          "p84": 6.71e-19,
          "uncertainty_lo": 1.04e-19,
          "uncertainty_hi": 1.23e-19,
          "bounds": [0, null]
        }
      }
    }
  ]
}
```

Amplitude parameters are in **physical units** (erg s⁻¹ cm⁻² Å⁻¹).
Uncertainties are from the 16th and 84th percentiles of the posterior
(±1σ equivalent).

### Load Results

Click **Load Results** to restore a saved fit. The GUI will recreate all
components, set parameter values, and draw the model on the current
spectrum. Open the same spectrum file first so the display scale matches.

## Plot Layout

The canvas has two panels:

- **Upper panel** — observed spectrum (black step histogram with error
  bars), individual component models (colored lines), composite model
  (red line), and optional 68% confidence band (red shading).
- **Lower panel** — residual (data − model) with error band (gray
  shading).

## Dependencies

- **[sagan](https://github.com/jyshangguan/SAGAN)** — the SAGAN spectral modeling library (must be installed separately)
- Python 3.9+
- PyQt5
- matplotlib
- astropy
- numpy, scipy
- emcee
- spectres

See `requirements.txt` for the full list with minimum versions.

## File Structure

```
sagan_gui_project/
├── sagan_gui/                 # GUI package
│   ├── main.py                # Main window
│   ├── canvas.py              # Matplotlib plot canvas
│   ├── param_panel.py         # Parameter editing panel
│   ├── drag_handler.py        # Interactive drag controls
│   ├── model_registry.py      # Model definitions and presets
│   ├── spectrum_loader.py     # FITS loader (JWST/IRAF/SDSS)
│   ├── fitting_worker.py      # MCMC thread
│   ├── post_mcmc.py           # Confidence bands, corner plots
│   └── run.py                 # Entry point
├── gui_example/               # Example data
│   ├── rubies-egs63-v4_...spec.fits   # JWST NIRSpec AGN spectrum
│   └── fit_results.json               # Saved fitting results
├── requirements.txt
├── README.md
└── AGENTS.md                  # Developer notes
```
