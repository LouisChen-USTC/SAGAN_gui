"""Load spectrum data from various FITS formats."""
import numpy as np
from astropy.io import fits


def load_spectrum(filepath):
    """Load spectrum from a FITS file.

    Returns dict with keys: wave, flux, err, metadata.
    wave is always returned in Angstroms.
    """
    hdul = fits.open(filepath)

    if len(hdul) > 1 and isinstance(hdul[1], fits.BinTableHDU):
        cols = [c.upper() for c in hdul[1].columns.names]
        cols_lower = hdul[1].columns.names
        col_map = {c.upper(): c_lower for c, c_lower in zip(cols, cols_lower)}

        if 'WAVE' in cols and 'FLUX' in cols:
            result = _load_jwst(hdul, col_map)
            hdul.close()
            return result

        if 'LOGLAM' in cols and 'FLUX' in cols:
            result = _load_sdss(hdul, col_map)
            hdul.close()
            return result

    hdu0 = hdul[0]
    if isinstance(hdu0, fits.PrimaryHDU) and hdu0.data is not None:
        if hdu0.data.ndim == 1:
            result = _load_iraf_1d(hdul)
            hdul.close()
            return result

    hdul.close()
    raise ValueError(f"Unrecognized spectrum format in {filepath}")


def _load_jwst(hdul, col_map):
    data = hdul[1].data
    wave = np.asarray(data[col_map['WAVE']], dtype=np.float64)
    flux = np.asarray(data[col_map['FLUX']], dtype=np.float64)

    if 'ERR' in col_map:
        err = np.asarray(data[col_map['ERR']], dtype=np.float64)
    elif 'FULL_ERR' in col_map:
        err = np.asarray(data[col_map['FULL_ERR']], dtype=np.float64)
    else:
        err = None

    if 'VALID' in col_map:
        valid = data[col_map['VALID']].astype(bool)
        wave = wave[valid]
        flux = flux[valid]
        if err is not None:
            err = err[valid]

    original_wave_unit = 'Angstrom'
    if len(wave) > 0 and np.nanmax(wave) < 100:
        wave = wave * 10000.0
        original_wave_unit = 'micron'

    if err is None:
        err = _estimate_errors(flux)

    metadata = {
        'format': 'JWST Binary Table',
        'object': hdul[1].header.get('SRCNAME', hdul[1].header.get('OBJECT', 'Unknown')),
        'original_wave_unit': original_wave_unit,
        'flux_unit': hdul[1].header.get('BUNIT', 'unknown'),
    }
    return {'wave': wave, 'flux': flux, 'err': err, 'metadata': metadata}


def _load_iraf_1d(hdul):
    header = hdul[0].header
    data = np.asarray(hdul[0].data, dtype=np.float64)

    crval1 = header.get('CRVAL1', 0.0)
    cdelt1 = header.get('CDELT1', header.get('CD1_1', 1.0))
    crpix1 = header.get('CRPIX1', 1.0)

    wave = crval1 + (np.arange(len(data)) - crpix1 + 1) * cdelt1

    valid = np.isfinite(data)
    wave = wave[valid]
    flux = data[valid]
    err = _estimate_errors(flux)

    metadata = {
        'format': 'IRAF 1D Image',
        'object': header.get('OBJECT', 'Unknown'),
        'wave_unit': 'Angstrom',
    }
    return {'wave': wave, 'flux': flux, 'err': err, 'metadata': metadata}


def _load_sdss(hdul, col_map):
    data = hdul[1].data
    wave = 10.0 ** np.asarray(data[col_map['LOGLAM']], dtype=np.float64)
    flux = np.asarray(data[col_map['FLUX']], dtype=np.float64)

    if 'IVAR' in col_map:
        ivar = np.asarray(data[col_map['IVAR']], dtype=np.float64)
        err = np.where(ivar > 0, 1.0 / np.sqrt(ivar), 0.0)
    else:
        err = _estimate_errors(flux)

    valid = np.isfinite(flux) & np.isfinite(wave) & (err > 0)
    wave = wave[valid]
    flux = flux[valid]
    err = err[valid]

    z = 0.0
    if len(hdul) > 2 and hasattr(hdul[2].data, '__len__') and len(hdul[2].data) > 0:
        z = hdul[2].data['z'][0]

    metadata = {
        'format': 'SDSS',
        'object': hdul[0].header.get('PLATE', 'Unknown'),
        'wave_unit': 'Angstrom',
        'z': z,
    }
    return {'wave': wave, 'flux': flux, 'err': err, 'metadata': metadata}


def _estimate_errors(flux):
    if len(flux) == 0:
        return np.array([])
    pos = flux[np.isfinite(flux)]
    if len(pos) == 0:
        return np.full_like(flux, 1e-10)
    return np.full_like(flux, np.nanstd(pos) * 0.1 + 1e-30)
