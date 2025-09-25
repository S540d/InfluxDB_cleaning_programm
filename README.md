# InfluxDB v1 Data Cleaner

Ein professionelles Tool zum Aufräumen und Konsolidieren von InfluxDB v1 Datenbanken. Dieses Tool hilft dabei, unorganisierte Messungen zu identifizieren, zu analysieren und sicher zu bereinigen.

## 🎯 Problem

InfluxDB v1 Datenbanken können mit der Zeit unübersichtlich werden:
- Messungen mit nur wenigen Datenpunkten
- Messungen, die zwischen verschiedenen Themen "gesprungen" sind
- Unlogische Anordnung und Benennung
- Verwaiste oder veraltete Messungen

## 🚀 Lösung

Dieses Tool bietet eine sichere, interaktive Lösung zur Datenbankbereinigung mit automatischen Backups und Bestätigungsdialogen.

## ✨ Features

### 🔍 Intelligente Analyse
- **Automatische Erkennung** problematischer Messungen
- **Last Entry Tracking** - Zeigt wann zuletzt Daten geschrieben wurden
- **Datenpunkt-Zählung** für jede Messung
- **Tag- und Field-Analyse**
- **Duplikaterkennung** basierend auf ähnlichen Namen
- **Hierarchie-Visualisierung** - Tree-ähnliche Darstellung der Measurement-Beziehungen

### 🖥️ Benutzerfreundliche Oberfläche
- **GUI-Modus** mit interaktiver Tabelle
- **Multi-Select** für Batch-Operationen
- **Detail-Ansicht** per Doppelklick
- **Command-Line Interface** für Automatisierung

### 🛡️ Sicherheitsfeatures
- **Automatische Backups** vor jeder Änderung
- **Bestätigungsdialoge** für alle kritischen Operationen
- **Detaillierte Logging** aller Aktivitäten
- **Rollback-fähige JSON-Backups**

### 🔧 Bereinigungsoperationen
- **Sichere Löschung** mit Backup und Bestätigung
- **Smart Merging** mehrerer Messungen mit Quell-Tracking
- **Bulk Cleanup** für Messungen mit wenigen Datenpunkten
- **Measurement Splitting** nach Tag-Werten

## 📦 Installation

### Voraussetzungen
- Python 3.7+
- InfluxDB v1.x Server
- Tkinter (für GUI, meist bereits installiert)

### Setup
```bash
# Repository klonen
git clone https://github.com/S540d/InfluxDB_cleaning_programm.git
cd InfluxDB_cleaning_programm

# Virtual Environment erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt
```

## 🎮 Verwendung

### GUI Modus (Empfohlen)
```bash
python influx_cleaner.py
```

**Workflow:**
1. **Verbindung** zu InfluxDB herstellen
2. **Analyze** klicken für automatische Problemerkennung
3. **Messungen auswählen** in der Tabelle
4. **Gewünschte Aktion** ausführen (Delete/Merge/Clean)

### Command Line Modus
```bash
# Analyse ausgeben
python influx_cleaner.py --host localhost --port 8086 --database mydb --no-gui

# Mit verschiedenen Parametern
python influx_cleaner.py --host influxdb.example.com --port 8086 --database sensors --no-gui
```

## 📋 GUI Bedienung

### Hauptfenster
- **Connection Panel**: InfluxDB Verbindungsparameter
- **Overview Tab**: Zusammenfassung der Analyseergebnisse
- **Measurements Tab**: Detaillierte Tabelle aller Messungen
- **Hierarchy Tab**: Tree-Darstellung der Measurement-Beziehungen

### Tabellen-Spalten
- **Measurement**: Name der Messung
- **Data Points**: Anzahl der Datenpunkte
- **Fields**: Anzahl der Fields
- **Tags**: Anzahl der Tags
- **Last Entry**: Zeitstempel des letzten Eintrags
- **Status**: Problemkategorie (OK, Low Data, Mixed Topics, Potential Duplicate)

### Aktionen
- **Delete Selected**: Ausgewählte Messungen sicher löschen
- **Merge Selected**: Messungen zusammenführen
- **Clean Low Data**: Messungen mit wenigen Datenpunkten bereinigen
- **Export Analysis**: Analyseergebnisse als JSON exportieren

### Hierarchy Tab
Die Hierarchy-Ansicht zeigt Measurements in einer baumartigen Struktur:

**Gruppierungen:**
- **Nach Namen**: Automatische Gruppierung nach gemeinsamen Präfixen (temp_kitchen, temp_living → temp/)
- **Nach Tags**: Gruppierung nach Tag-Schlüsseln und -Werten
- **Nach Themen**: Intelligente Kategorisierung (sensor, system, power, etc.)

**Navigation:**
- **Expandierbar**: Klickbare Knoten zum Auf-/Zuklappen
- **Statistiken**: Zeigt Anzahl, Gesamtpunkte und neuesten Eintrag pro Gruppe
- **Detail-Ansicht**: Doppelklick auf 📊 Symbole für Measurement-Details

**Nutzen:**
- Visualisiert Beziehungen zwischen Measurements
- Identifiziert logische Gruppierungen
- Hilft bei Merge-Entscheidungen
- Zeigt Naming-Patterns auf

## 🔧 Konfiguration

### Verbindungsparameter
- **Host**: InfluxDB Server IP/Hostname (Standard: localhost)
- **Port**: InfluxDB Port (Standard: 8086)
- **Database**: Datenbankname
- **Username/Password**: Optional für authentifizierte Verbindungen

### Erweiterte Einstellungen
Die Schwellenwerte für problematische Messungen können im Code angepasst werden:
```python
# In influx_cleaner.py, analyze_measurement Methode
min_points = 10  # Mindestanzahl Datenpunkte
```

## 📁 Projektstruktur

```
influxDB_cleaning_programm/
├── influx_cleaner.py      # Hauptprogramm mit GUI
├── cleaner_core.py        # Bereinigungsfunktionen
├── requirements.txt       # Python Dependencies
├── README.md             # Diese Datei
├── .gitignore           # Git Ignore-Regeln
└── venv/               # Virtual Environment (lokal)
```

## 🔒 Sicherheit

### Backup-System
- Automatische JSON-Backups vor jeder Änderung
- Zeitstempel-basierte Dateinamen
- Vollständige Wiederherstellbarkeit
- Backup-Dateien werden von Git ignoriert

### Bestätigungen
- Alle kritischen Operationen erfordern explizite Bestätigung
- Detaillierte Vorschau der betroffenen Messungen
- Abbruchbare Operationen

## 🐛 Troubleshooting

### Häufige Probleme

**"ModuleNotFoundError: No module named '_tkinter'"**
```bash
# macOS
brew install python-tk

# Ubuntu/Debian
sudo apt-get install python3-tk

# CentOS/RHEL
sudo yum install tkinter
```

**"Connection refused"**
- InfluxDB Server läuft und ist erreichbar
- Firewall-Einstellungen prüfen
- Korrekte Host/Port-Parameter

**"Database not found"**
- Datenbankname korrekt eingeben
- Benutzerrechte für Datenbank prüfen

## 🤝 Entwicklung

### Code-Struktur
- `InfluxDBAnalyzer`: Datenbank-Analyse und -Verbindung
- `InfluxDBCleaner`: Bereinigungsoperationen
- `InfluxCleanerGUI`: Grafische Benutzeroberfläche

### Beitragen
1. Fork des Repositories
2. Feature-Branch erstellen
3. Änderungen implementieren
4. Tests hinzufügen
5. Pull Request erstellen

## 📄 Lizenz

MIT License - Siehe LICENSE Datei für Details

## ⚠️ Haftungsausschluss

Dieses Tool führt Schreiboperationen auf InfluxDB-Datenbanken aus. Obwohl automatische Backups erstellt werden, wird empfohlen, vor wichtigen Operationen vollständige Datenbank-Backups zu erstellen.

## 📞 Support

Bei Problemen oder Fragen:
1. GitHub Issues verwenden
2. Logs prüfen für detaillierte Fehlermeldungen
3. Backup-Dateien für Wiederherstellung nutzen

---

🤖 *Entwickelt mit Claude Code für effiziente InfluxDB v1 Datenverwaltung*