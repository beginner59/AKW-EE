from __future__ import annotations

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from model import PHS_ENERGY_GWH, PHS_POWER_GW, REST_TWH, SimulationInputs, run_simulation

st.set_page_config(page_title='AKW + EE Demo', layout='wide')

st.title('AKW + EE Demo')
st.markdown(
    'Diese Demo illustriert vereinfacht, dass zusätzliche AKW-Leistung in einem stark erneuerbaren, '
    'dekarbonisierten Stromsystem zu mehr nicht nutzbarem Strom führen kann.'
)

with st.sidebar:
    st.header('Eingaben')
    pv_twh = st.slider('PV [TWh/Jahr]', min_value=30.0, max_value=60.0, value=45.0, step=1.0)
    wind_twh = st.slider('Wind [TWh/Jahr]', min_value=0.2, max_value=10.0, value=4.0, step=0.1)
    efficiency_twh = st.slider('Effizienzmassnahmen [TWh/Jahr]', min_value=0.0, max_value=15.0, value=5.0, step=0.5)
    nuclear_gw = st.slider('AKW-Leistung [GW]', min_value=0.0, max_value=3.0, value=1.6, step=0.1)
    battery_gwh = st.slider('Batteriespeicher [GWh]', min_value=50, max_value=200, value=100, step=10)
    balance_days = st.slider('Bilanzfenster [Tage]', min_value=2, max_value=5, value=3, step=1)

    st.markdown('---')
    st.caption('Fix eingebaut: Restliche Anlagen, Pumpspeicher, Speicherwasserkraft (Okt-März), kein Export')
    st.caption(f'Restliche Anlagen: {REST_TWH:.1f} TWh/Jahr')
    st.caption(f'Pumpspeicher: {PHS_ENERGY_GWH:.0f} GWh, {PHS_POWER_GW:.1f} GW')

inputs = SimulationInputs(
    pv_twh=pv_twh,
    wind_twh=wind_twh,
    efficiency_twh=efficiency_twh,
    nuclear_gw=nuclear_gw,
    battery_gwh=float(battery_gwh),
    balance_days=balance_days,
)
results = run_simulation(inputs)

c1, c2, c3, c4 = st.columns(4)
c1.metric('Abregelung', f'{results.curtailed_twh:.2f} TWh/Jahr')
c2.metric('Jahreslast nach Effizienz', f'{results.annual_load_after_eff_twh:.1f} TWh')
c3.metric('Speicherwasserkraft eingesetzt', f'{results.hydro_used_twh:.2f} TWh')
c4.metric('Rest-Unterdeckung', f'{results.unmet_twh:.2f} TWh')

st.subheader('Jährliche Strommengen')
summary_df = pd.DataFrame({
    'Kategorie': ['Last vor Effizienz', 'Last nach Effizienz', 'Gesamtproduktion', 'Abregelung', 'Speicherwasserkraft', 'Rest-Unterdeckung'],
    'TWh': [
        results.annual_load_twh,
        results.annual_load_after_eff_twh,
        results.annual_generation_twh,
        results.curtailed_twh,
        results.hydro_used_twh,
        results.unmet_twh,
    ]
})
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.subheader('Produktion nach Technologie')
gen_df = pd.DataFrame({
    'Technologie': list(results.generation_breakdown_twh.keys()),
    'TWh': list(results.generation_breakdown_twh.values()),
})
st.dataframe(gen_df, use_container_width=True, hide_index=True)

st.subheader('Zeitreihe für ausgewähltes Fenster')
start = results.hourly['timestamp'].min()
end = results.hourly['timestamp'].max() - pd.Timedelta(days=7)
default_start = pd.Timestamp(results.hourly['timestamp'].min()) + pd.Timedelta(days=15)
window_start = st.date_input('Startdatum', value=default_start.date(), min_value=start.date(), max_value=end.date())
window_hours = balance_days * 24

view = results.hourly[
    (results.hourly['timestamp'] >= pd.Timestamp(window_start))
    & (results.hourly['timestamp'] < pd.Timestamp(window_start) + pd.Timedelta(hours=window_hours))
].copy()

view['prod_with_hydro_mwh'] = view['gross_generation_mwh'] + view['hydro_dispatch_mwh']

fig1, ax1 = plt.subplots(figsize=(10, 4))
ax1.plot(view['timestamp'], view['load_after_eff_mwh'] / 1e3, label='Last nach Effizienz [GWh/h]')
ax1.plot(view['timestamp'], view['gross_generation_mwh'] / 1e3, label='Produktion ohne Speicherwasserkraft [GWh/h]')
ax1.plot(view['timestamp'], view['prod_with_hydro_mwh'] / 1e3, label='Produktion inkl. Speicherwasserkraft [GWh/h]')
ax1.set_ylabel('GWh pro Stunde')
ax1.legend()
ax1.grid(True, alpha=0.3)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %Hh'))
fig1.autofmt_xdate()
st.pyplot(fig1)

st.subheader('Speicherfüllstände')
fig2, ax2 = plt.subplots(figsize=(10, 4))
ax2.plot(view['timestamp'], view['battery_soc_mwh'] / 1e3, label='Batterie [GWh]')
ax2.plot(view['timestamp'], view['phs_soc_mwh'] / 1e3, label='Pumpspeicher [GWh]')
ax2.set_ylabel('GWh')
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %Hh'))
fig2.autofmt_xdate()
st.pyplot(fig2)

st.subheader('Monatliche Abregelung')
monthly = results.hourly.groupby('month', as_index=False)['curtailed_mwh'].sum()
fig3, ax3 = plt.subplots(figsize=(10, 4))
ax3.bar(monthly['month'], monthly['curtailed_mwh'] / 1e6)
ax3.set_xlabel('Monat')
ax3.set_ylabel('Abregelung [TWh]')
ax3.set_xticks(range(1, 13))
ax3.grid(True, axis='y', alpha=0.3)
st.pyplot(fig3)

with st.expander('Vereinfachungen und Annahmen'):
    st.markdown(
        '- Synthetische Stundenprofile für Last, PV, Wind, Restproduktion und AKW.\n'
        '- Batteriespeicher mit 1C Lade-/Entladeleistung und 100 % Wirkungsgrad.\n'
        '- Pumpspeicher mit fixer heutiger Grössenordnung.\n'
        '- Speicherwasserkraft nur Oktober bis März mit maximal 8 TWh Winterenergie.\n'
        '- Kein Export. Verbleibende Überschüsse werden abgeregelt.\n'
        '- Das Bilanzfenster wird in dieser ersten Version didaktisch für die Anzeige genutzt; '
        'die Speicherbilanz läuft stündlich und rollierend über das ganze Jahr.'
    )
