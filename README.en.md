# InfluxDB v1 Data Cleaner

A professional tool for cleaning up and consolidating InfluxDB v1 databases. This tool helps identify, analyze, and safely clean unorganized measurements.

## 🎯 Problem

InfluxDB v1 databases can become cluttered over time:
- Measurements with only a few data points
- Measurements that have "jumped" between different topics
- Illogical arrangement and naming
- Orphaned or outdated measurements

## 🚀 Solution

This tool provides a safe, interactive solution for database cleanup with automatic backups and confirmation dialogs.

## ✨ Features

### 🔍 Intelligent Analysis
- **Automatic detection** of problematic measurements
- **Last Entry Tracking** - Shows when data was last written
- **Data point counting** for each measurement
- **Tag and field analysis**
- **Duplicate detection** based on similar names
- **Hierarchy visualization** - Tree-like representation of measurement relationships

### 🖥️ User-Friendly Interface
- **GUI mode** with interactive table
- **Multi-select** for batch operations
- **Detail view** via double-click
- **Command-line interface** for automation

### 🛡️ Security Features
- **Automatic backups** before each change
- **Confirmation dialogs** for all critical operations
- **Detailed logging** of all activities
- **Rollback-capable JSON backups**

### 🔧 Cleanup Operations
- **Safe deletion** with backup and confirmation
- **Smart merging** of multiple measurements with source tracking
- **Bulk cleanup** for measurements with few data points
- **Measurement splitting** by tag values

## 📦 Installation

### Prerequisites
- Python 3.7+
- InfluxDB v1.x Server
- Tkinter (for GUI, usually already installed)

### Setup
```bash
# Clone repository
git clone https://github.com/S540d/InfluxDB_cleaning_programm.git
cd InfluxDB_cleaning_programm

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## 🎮 Usage

### GUI Mode (Recommended)
```bash
python influx_cleaner.py
```

**Workflow:**
1. **Connect** to InfluxDB
2. Click **Analyze** for automatic problem detection
3. **Select measurements** in the table
4. **Execute desired action** (Delete/Merge/Clean)

### Command Line Mode
```bash
# Output analysis
python influx_cleaner.py --host localhost --port 8086 --database mydb --no-gui

# With different parameters
python influx_cleaner.py --host influxdb.example.com --port 8086 --database sensors --no-gui
```

## 📋 GUI Operation

### Main Window
- **Connection Panel**: InfluxDB connection parameters
- **Overview Tab**: Summary of analysis results
- **Measurements Tab**: Detailed table of all measurements
- **Hierarchy Tab**: Tree representation of measurement relationships

### Table Columns
- **Measurement**: Name of the measurement
- **Data Points**: Number of data points
- **Fields**: Number of fields
- **Tags**: Number of tags
- **Last Entry**: Timestamp of last entry
- **Status**: Problem category (OK, Low Data, Mixed Topics, Potential Duplicate)

### Actions
- **Delete Selected**: Safely delete selected measurements
- **Merge Selected**: Merge measurements
- **Clean Low Data**: Clean measurements with few data points
- **Export Analysis**: Export analysis results as JSON

### Hierarchy Tab
The Hierarchy view shows measurements in a tree-like structure:

**Groupings:**
- **By Name**: Automatic grouping by common prefixes (temp_kitchen, temp_living → temp/)
- **By Tags**: Grouping by tag keys and values
- **By Topics**: Intelligent categorization (sensor, system, power, etc.)

**Navigation:**
- **Expandable**: Clickable nodes for expand/collapse
- **Statistics**: Shows count, total points, and latest entry per group
- **Detail View**: Double-click on 📊 symbols for measurement details

**Benefits:**
- Visualizes relationships between measurements
- Identifies logical groupings
- Helps with merge decisions
- Shows naming patterns

## 🔧 Configuration

### Connection Parameters
- **Host**: InfluxDB Server IP/Hostname (Default: localhost)
- **Port**: InfluxDB Port (Default: 8086)
- **Database**: Database name
- **Username/Password**: Optional for authenticated connections

### Advanced Settings
Thresholds for problematic measurements can be adjusted in the code:
```python
# In influx_cleaner.py, analyze_measurement method
min_points = 10  # Minimum number of data points
```

## 📁 Project Structure

```
influxDB_cleaning_programm/
├── influx_cleaner.py      # Main program with GUI
├── cleaner_core.py        # Cleanup functions
├── requirements.txt       # Python dependencies
├── README.md             # German documentation
├── README.en.md          # English documentation
├── .gitignore           # Git ignore rules
└── venv/               # Virtual environment (local)
```

## 🔒 Security

### Backup System
- Automatic JSON backups before each change
- Timestamp-based filenames
- Complete recoverability
- Backup files are ignored by Git

### Confirmations
- All critical operations require explicit confirmation
- Detailed preview of affected measurements
- Abortable operations

## 🐛 Troubleshooting

### Common Issues

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
- InfluxDB server is running and reachable
- Check firewall settings
- Correct host/port parameters

**"Database not found"**
- Enter correct database name
- Check user permissions for database

## 🤝 Development

### Code Structure
- `InfluxDBAnalyzer`: Database analysis and connection
- `InfluxDBCleaner`: Cleanup operations
- `InfluxCleanerGUI`: Graphical user interface

### Contributing
1. Fork the repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Create pull request

## 📄 License

MIT License - See LICENSE file for details

## ⚠️ Disclaimer

This tool performs write operations on InfluxDB databases. Although automatic backups are created, it is recommended to create complete database backups before important operations.

## 📞 Support

For problems or questions:
1. Use GitHub Issues
2. Check logs for detailed error messages
3. Use backup files for recovery

---

🤖 *Developed with Claude Code for efficient InfluxDB v1 data management*