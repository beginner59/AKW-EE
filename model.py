from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / 'data'

# Fixed assumptions for prototype v1
BASE_LOAD_TWH = 92.0
REST_TWH = 18.0
PHS_ENERGY_GWH = 30.0
PHS_POWER_GW = 3.0
HYDRO_SEASONAL_MAX_TWH = 8.0  # October-March
WINTER_MONTHS = {10, 11, 12, 1, 2, 3}


@dataclass
class SimulationInputs:
    pv_twh: float
    wind_twh: float
    efficiency_twh: float
    nuclear_gw: float
    battery_gwh: float
    balance_days: int


@dataclass
class SimulationResults:
    hourly: pd.DataFrame
    curtailed_twh: float
    unmet_twh: float
    hydro_used_twh: float
    final_battery_gwh: float
    final_phs_gwh: float
    annual_load_twh: float
    annual_load_after_eff_twh: float
    annual_generation_twh: float
    generation_breakdown_twh: dict



def load_profiles() -> dict[str, pd.DataFrame]:
    profiles = {}
    for name in ['load', 'pv', 'wind', 'rest', 'nuclear']:
        path = DATA_DIR / f'{name}_profile.csv'
        df = pd.read_csv(path, parse_dates=['timestamp'])
        profiles[name] = df
    return profiles



def _apply_efficiency(load_mwh: np.ndarray, efficiency_twh: float) -> np.ndarray:
    annual_load_twh = load_mwh.sum() / 1e6
    reduction_frac = min(max(efficiency_twh / annual_load_twh, 0.0), 0.95)
    return load_mwh * (1.0 - reduction_frac)



def run_simulation(inputs: SimulationInputs) -> SimulationResults:
    profiles = load_profiles()
    timestamps = profiles['load']['timestamp']

    load_mwh = profiles['load']['profile'].to_numpy() * BASE_LOAD_TWH * 1e6
    load_after_eff_mwh = _apply_efficiency(load_mwh, inputs.efficiency_twh)

    pv_mwh = profiles['pv']['profile'].to_numpy() * inputs.pv_twh * 1e6
    wind_mwh = profiles['wind']['profile'].to_numpy() * inputs.wind_twh * 1e6
    rest_mwh = profiles['rest']['profile'].to_numpy() * REST_TWH * 1e6
    nuclear_mwh = profiles['nuclear']['profile'].to_numpy() * inputs.nuclear_gw * 8760.0 * 1e3

    gross_generation_mwh = pv_mwh + wind_mwh + rest_mwh + nuclear_mwh

    n = len(timestamps)
    battery_soc = 0.5 * inputs.battery_gwh * 1e3
    phs_soc = 0.5 * PHS_ENERGY_GWH * 1e3
    hydro_remaining_mwh = HYDRO_SEASONAL_MAX_TWH * 1e6

    battery_power_mwh = inputs.battery_gwh * 1e3  # 1C over 1h
    phs_power_mwh = PHS_POWER_GW * 1e3

    records: list[dict] = []
    curtailed_mwh = 0.0
    unmet_mwh = 0.0
    hydro_used_mwh = 0.0

    for i in range(n):
        ts = timestamps.iloc[i]
        net_mwh = gross_generation_mwh[i] - load_after_eff_mwh[i]

        batt_charge = batt_discharge = 0.0
        phs_charge = phs_discharge = 0.0
        hydro_dispatch = 0.0
        curtailed = 0.0
        unmet = 0.0

        if net_mwh >= 0:
            batt_charge = min(net_mwh, battery_power_mwh, inputs.battery_gwh * 1e3 - battery_soc)
            battery_soc += batt_charge
            net_mwh -= batt_charge

            phs_charge = min(net_mwh, phs_power_mwh, PHS_ENERGY_GWH * 1e3 - phs_soc)
            phs_soc += phs_charge
            net_mwh -= phs_charge

            curtailed = max(net_mwh, 0.0)
            curtailed_mwh += curtailed
        else:
            deficit = -net_mwh

            batt_discharge = min(deficit, battery_power_mwh, battery_soc)
            battery_soc -= batt_discharge
            deficit -= batt_discharge

            phs_discharge = min(deficit, phs_power_mwh, phs_soc)
            phs_soc -= phs_discharge
            deficit -= phs_discharge

            if ts.month in WINTER_MONTHS and hydro_remaining_mwh > 0:
                hydro_dispatch = min(deficit, hydro_remaining_mwh)
                hydro_remaining_mwh -= hydro_dispatch
                hydro_used_mwh += hydro_dispatch
                deficit -= hydro_dispatch

            unmet = max(deficit, 0.0)
            unmet_mwh += unmet

        records.append({
            'timestamp': ts,
            'load_mwh': load_mwh[i],
            'load_after_eff_mwh': load_after_eff_mwh[i],
            'pv_mwh': pv_mwh[i],
            'wind_mwh': wind_mwh[i],
            'rest_mwh': rest_mwh[i],
            'nuclear_mwh': nuclear_mwh[i],
            'gross_generation_mwh': gross_generation_mwh[i],
            'battery_soc_mwh': battery_soc,
            'phs_soc_mwh': phs_soc,
            'battery_charge_mwh': batt_charge,
            'battery_discharge_mwh': batt_discharge,
            'phs_charge_mwh': phs_charge,
            'phs_discharge_mwh': phs_discharge,
            'hydro_dispatch_mwh': hydro_dispatch,
            'curtailed_mwh': curtailed,
            'unmet_mwh': unmet,
        })

    hourly = pd.DataFrame(records)
    hourly['month'] = hourly['timestamp'].dt.month

    return SimulationResults(
        hourly=hourly,
        curtailed_twh=curtailed_mwh / 1e6,
        unmet_twh=unmet_mwh / 1e6,
        hydro_used_twh=hydro_used_mwh / 1e6,
        final_battery_gwh=battery_soc / 1e3,
        final_phs_gwh=phs_soc / 1e3,
        annual_load_twh=load_mwh.sum() / 1e6,
        annual_load_after_eff_twh=load_after_eff_mwh.sum() / 1e6,
        annual_generation_twh=(gross_generation_mwh.sum() + hydro_used_mwh) / 1e6,
generation_breakdown_twh={
    'PV': pv_mwh.sum() / 1e6,
    'Wind': wind_mwh.sum() / 1e6,
    'AKW': nuclear_mwh.sum() / 1e6,
    'Restliche Anlagen': rest_mwh.sum() / 1e6,
    'Speicherwasserkraft': hydro_used_mwh / 1e6,
},
    )
