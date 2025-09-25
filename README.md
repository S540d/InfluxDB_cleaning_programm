# InfluxDB v1 Data Cleaner

Ein Tool zum Aufräumen und Konsolidieren von InfluxDB v1 Datenbanken.

## Features

- Analysiert Messungen mit wenigen Datenpunkten
- Identifiziert Messungen, die zwischen Themen gesprungen sind
- GUI und Command-Line Interface
- Sicherheitsfunktionen für Datenbackup
- Export der Analyseergebnisse

## Installation

```bash
pip install -r requirements.txt
```

## Verwendung

### GUI Modus
```bash
python influx_cleaner.py
```

### Command Line Modus
```bash
python influx_cleaner.py --host localhost --port 8086 --database mydb --no-gui
```

## Funktionen

1. **Verbindung zur InfluxDB**: Konfigurierbare Verbindungsparameter
2. **Analyse**: Automatische Erkennung problematischer Messungen
3. **Bereinigung**: Tools zum Aufräumen und Konsolidieren
4. **Export**: Analyseergebnisse als JSON exportieren