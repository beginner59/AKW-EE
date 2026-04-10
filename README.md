# AKW + EE Demo

Ein erster Streamlit-Prototyp fuer eine didaktische Demo zur Frage, wie zusaetzliche AKW-Leistung mit einem stark erneuerbaren Stromsystem zusammenpasst.

## Start lokal

```bash
pip install -r requirements.txt
python generate_profiles.py
streamlit run app.py
```

## Inhalt

- `generate_profiles.py`: erzeugt synthetische CSV-Profile mit 8760 Stundenwerten
- `model.py`: Stundenbilanz mit Batterie, Pumpspeicher und Speicherwasserkraft
- `app.py`: Streamlit-Oberflaeche

## Hinweise

- Die synthetischen Profile koennen spaeter durch reale CSV-Dateien ersetzt werden.
- Das Bilanzfenster ist in dieser ersten Version noch keine harte rechnerische Nebenbedingung.
