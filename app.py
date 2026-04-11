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
    pv_twh = st.slider('PV [TWh/Jahr]', min_value=30.0, max_value=60.0, value=54.0, step=1.0)
    wind_twh = st.slider('Wind [TWh/Jahr]', min_value=0.2, max_value=10.0, value=4.0, step=0.1)
    efficiency_twh = st.slider('Effizienzmassnahmen [TWh/Jahr]', min_value=0.0, max_value=15.0, value=9.5, step=0.5)
    nuclear_gw = st.slider('AKW-Leistung [GW]', min_value=0.0, max_value=3.0, value=0.0, step=0.1)
    battery_gwh = st.slider('Batteriespeicher [GWh]', min_value=50, max_value=200, value=100, step=10)

    st.markdown('---')
    st.caption('Fix eingebaut: Pumpspeicher, Speicherwasserkraft Sommer und Speicherwasserkraft Winter, kein Export')
    st.caption(f'Restliche Anlagen ohne Speicherwasserkraft: {REST_TWH:.1f} TWh/Jahr')
    st.caption('Speicherwasserkraft Sommer: 9.8 TWh/Jahr')
    st.caption('Speicherwasserkraft Winter flexibel: max. 8.0 TWh')
    st.caption(f'Pumpspeicher: {PHS_ENERGY_GWH:.0f} GWh, {PHS_POWER_GW:.1f} GW')

inputs = SimulationInputs(
    pv_twh=pv_twh,
    wind_twh=wind_twh,
    efficiency_twh=efficiency_twh,
    nuclear_gw=nuclear_gw,
    battery_gwh=float(battery_gwh),
)
results = run_simulation(inputs)

c1, c2, c3, c4 = st.columns(4)
c1.metric('Abregelung', f'{results.curtailed_twh:.2f} TWh/Jahr')
c2.metric('Jahreslast nach Effizienz', f'{results.annual_load_after_eff_twh:.1f} TWh')
c3.metric('Speicherwasserkraft Winter eingesetzt', f'{results.hydro_used_twh:.2f} TWh')
c4.metric('Rest-Unterdeckung', f'{results.unmet_twh:.2f} TWh')

st.subheader('Jährliche Strommengen')
summary_df = pd.DataFrame({
    'Kategorie': [
        'Last vor Effizienz',
        'Last nach Effizienz',
        'Gesamtproduktion inkl. Speicherwasserkraft',
        'Abregelung',
        'Speicherwasserkraft Winter eingesetzt',
        'Rest-Unterdeckung',
    ],
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
window_hours = 72

view = results.hourly[
    (results.hourly['timestamp'] >= pd.Timestamp(window_start))
    & (results.hourly['timestamp'] < pd.Timestamp(window_start) + pd.Timedelta(hours=window_hours))
].copy()

view['prod_with_hydro_mwh'] = view['gross_generation_mwh'] + view['hydro_dispatch_mwh']

fig1, ax1 = plt.subplots(figsize=(10, 4))
ax1.plot(view['timestamp'], view['load_after_eff_mwh'] / 1e3, label='Last nach Effizienz [GWh/h]')
ax1.plot(view['timestamp'], view['gross_generation_mwh'] / 1e3, label='Produktion inkl. Speicherwasserkraft Sommer [GWh/h]')
ax1.plot(view['timestamp'], view['prod_with_hydro_mwh'] / 1e3, label='Produktion inkl. Speicherwasserkraft Sommer + Winter [GWh/h]')
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

st.subheader('Monatsbilanz nach Technologien')

month_names = {
    1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April',
    5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'
}

selected_month = st.selectbox(
    'Monat auswählen',
    options=list(month_names.keys()),
    format_func=lambda m: month_names[m],
    index=0,
)

month_view = results.hourly[results.hourly['month'] == selected_month].copy()

monthly_load_twh = month_view['load_after_eff_mwh'].sum() / 1e6
monthly_pv_twh = month_view['pv_mwh'].sum() / 1e6
monthly_wind_twh = month_view['wind_mwh'].sum() / 1e6
monthly_nuclear_twh = month_view['nuclear_mwh'].sum() / 1e6
monthly_rest_twh = month_view['rest_mwh'].sum() / 1e6
monthly_hydro_summer_twh = month_view['hydro_summer_mwh'].sum() / 1e6
monthly_hydro_winter_twh = month_view['hydro_dispatch_mwh'].sum() / 1e6

fig4, ax4 = plt.subplots(figsize=(9, 5))

bottom = 0.0
for label, value in [
    ('PV', monthly_pv_twh),
    ('Wind', monthly_wind_twh),
    ('AKW', monthly_nuclear_twh),
    ('Restliche Anlagen', monthly_rest_twh),
    ('Speicherwasserkraft Sommer', monthly_hydro_summer_twh),
    ('Speicherwasserkraft Winter', monthly_hydro_winter_twh),
]:
    ax4.bar('Produktion', value, bottom=bottom, label=label)
    bottom += value

ax4.bar('Strombedarf', monthly_load_twh, label='Strombedarf')
ax4.set_ylabel('TWh')
ax4.set_title(f'Monatsbilanz {month_names[selected_month]}')
ax4.grid(True, axis='y', alpha=0.3)
ax4.legend()
st.pyplot(fig4)

st.subheader('Stündliche Zeitreihe für den gewählten Monat')

month_view['total_generation_mwh'] = (
    month_view['gross_generation_mwh'] + month_view['hydro_dispatch_mwh']
)

fig5, ax5 = plt.subplots(figsize=(12, 4))
ax5.plot(
    month_view['timestamp'],
    month_view['load_after_eff_mwh'] / 1e3,
    label='Strombedarf [GWh/h]'
)
ax5.plot(
    month_view['timestamp'],
    month_view['total_generation_mwh'] / 1e3,
    label='Produktion [GWh/h]'
)
ax5.fill_between(
    month_view['timestamp'],
    0,
    month_view['curtailed_mwh'] / 1e3,
    where=(month_view['curtailed_mwh'] > 0),
    alpha=0.3,
    label='Abregelung [GWh/h]'
)
ax5.set_ylabel('GWh pro Stunde')
ax5.set_title(f'Stündlicher Verlauf {month_names[selected_month]}')
ax5.grid(True, alpha=0.3)
ax5.legend()
ax5.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %Hh'))
fig5.autofmt_xdate()
st.pyplot(fig5)

monthly_curtailed_twh = month_view['curtailed_mwh'].sum() / 1e6
st.caption(f'Abregelung im {month_names[selected_month]}: {monthly_curtailed_twh:.2f} TWh')

with st.expander('Vereinfachungen und Annahmen'):
    st.markdown(
        '- Synthetische Stundenprofile für Last, PV, Wind, Restproduktion und AKW.\n'
        '- Batteriespeicher mit 1C Lade-/Entladeleistung und 100 % Wirkungsgrad.\n'
        '- Pumpspeicher mit fixer heutiger Grössenordnung.\n'
        '- Speicherwasserkraft Sommer als feste Produktion von 9.8 TWh im Sommerhalbjahr.\n'
        '- Speicherwasserkraft Winter nur Oktober bis März mit maximal 8 TWh Winterenergie.\n'
        '- Kein Export. Verbleibende Überschüsse werden abgeregelt.\n'
        '- Die Speicherbilanz läuft stündlich und rollierend über das ganze Jahr.\n'
        '- Kurzfristige Verschiebung wird über Batterie und Pumpspeicher abgebildet, nicht über ein separates Bilanzfenster.'
    )
