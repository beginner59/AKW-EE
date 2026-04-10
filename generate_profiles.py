from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

YEAR = 2025  # non-leap year
HOURS = 8760
OUTDIR = Path(__file__).resolve().parent / 'data'


def build_time_index() -> pd.DatetimeIndex:
    return pd.date_range(f"{YEAR}-01-01 00:00", periods=HOURS, freq='h')


def normalize_to_sum(arr: np.ndarray, target: float = 1.0) -> np.ndarray:
    total = float(arr.sum())
    if total <= 0:
        raise ValueError('Profile sum must be positive.')
    return arr * (target / total)


def seasonal_factor(day_of_year: np.ndarray, peak_day: int, amplitude: float, baseline: float = 1.0) -> np.ndarray:
    return baseline + amplitude * np.cos(2 * math.pi * (day_of_year - peak_day) / 365.0)


def create_load_profile(idx: pd.DatetimeIndex) -> pd.DataFrame:
    hod = idx.hour.to_numpy()
    dow = idx.dayofweek.to_numpy()
    doy = idx.dayofyear.to_numpy()

    winter = seasonal_factor(doy, peak_day=15, amplitude=0.17, baseline=1.0)
    morning = np.exp(-0.5 * ((hod - 8) / 2.5) ** 2)
    evening = 1.25 * np.exp(-0.5 * ((hod - 19) / 3.0) ** 2)
    night_base = 0.72 + 0.05 * np.cos(2 * math.pi * (hod - 3) / 24.0)
    weekend = np.where(dow >= 5, 0.93, 1.0)

    raw = winter * weekend * (night_base + 0.18 * morning + 0.28 * evening)
    raw = normalize_to_sum(raw, target=1.0)

    return pd.DataFrame({
        'timestamp': idx,
        'profile': raw,
    })


def create_pv_profile(idx: pd.DatetimeIndex) -> pd.DataFrame:
    hod = idx.hour.to_numpy()
    doy = idx.dayofyear.to_numpy()

    seasonal = np.clip(seasonal_factor(doy, peak_day=172, amplitude=0.75, baseline=0.95), 0.03, None)
    daylight = np.maximum(0.0, np.sin(math.pi * (hod - 6) / 12.0)) ** 1.6
    raw = seasonal * daylight
    raw = normalize_to_sum(raw, target=1.0)

    return pd.DataFrame({
        'timestamp': idx,
        'profile': raw,
    })


def create_wind_profile(idx: pd.DatetimeIndex) -> pd.DataFrame:
    hod = idx.hour.to_numpy()
    doy = idx.dayofyear.to_numpy()
    rng = np.random.default_rng(42)

    seasonal = np.clip(seasonal_factor(doy, peak_day=15, amplitude=0.28, baseline=1.0), 0.35, None)
    diurnal = 0.96 + 0.06 * np.cos(2 * math.pi * (hod - 1) / 24.0)
    synoptic = rng.normal(1.0, 0.18, size=len(idx))
    synoptic = pd.Series(synoptic).rolling(12, center=True, min_periods=1).mean().to_numpy()
    raw = np.clip(seasonal * diurnal * synoptic, 0.02, None)
    raw = normalize_to_sum(raw, target=1.0)

    return pd.DataFrame({
        'timestamp': idx,
        'profile': raw,
    })


def create_rest_profile(idx: pd.DatetimeIndex) -> pd.DataFrame:
    doy = idx.dayofyear.to_numpy()
    hod = idx.hour.to_numpy()

    river = np.clip(seasonal_factor(doy, peak_day=165, amplitude=0.25, baseline=0.95), 0.45, None)
    biomass_wte = np.full(len(idx), 0.55)
    small_diurnal = 1.0 + 0.02 * np.cos(2 * math.pi * (hod - 12) / 24.0)

    raw = (0.7 * river + 0.3 * biomass_wte) * small_diurnal
    raw = normalize_to_sum(raw, target=1.0)

    return pd.DataFrame({
        'timestamp': idx,
        'profile': raw,
    })


def create_nuclear_profile(idx: pd.DatetimeIndex) -> pd.DataFrame:
    raw = np.ones(len(idx), dtype=float)

    def outage(start: str, end: str, availability: float) -> None:
        mask = (idx >= pd.Timestamp(start)) & (idx < pd.Timestamp(end))
        raw[mask] = availability

    outage(f'{YEAR}-05-01 00:00', f'{YEAR}-05-29 00:00', 0.0)
    outage(f'{YEAR}-09-15 00:00', f'{YEAR}-10-06 00:00', 0.45)
    outage(f'{YEAR}-01-17 00:00', f'{YEAR}-01-20 00:00', 0.7)
    outage(f'{YEAR}-12-03 00:00', f'{YEAR}-12-05 12:00', 0.75)

    raw = normalize_to_sum(raw, target=1.0)
    return pd.DataFrame({
        'timestamp': idx,
        'profile': raw,
    })


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    idx = build_time_index()

    creators = {
        'load_profile.csv': create_load_profile,
        'pv_profile.csv': create_pv_profile,
        'wind_profile.csv': create_wind_profile,
        'rest_profile.csv': create_rest_profile,
        'nuclear_profile.csv': create_nuclear_profile,
    }

    for filename, creator in creators.items():
        df = creator(idx)
        df.to_csv(OUTDIR / filename, index=False)

    print(f'Wrote {len(creators)} profile files to {OUTDIR}')


if __name__ == '__main__':
    main()
