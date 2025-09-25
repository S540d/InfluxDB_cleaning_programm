#!/usr/bin/env python3
"""
InfluxDB v1 Data Cleaning and Consolidation Tool

This tool helps clean up InfluxDB v1 databases by:
- Analyzing measurements with few data points
- Identifying measurements that jumped between topics
- Consolidating and reorganizing measurements logically
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from influxdb import InfluxDBClient
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText
import concurrent.futures
import threading
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class InfluxDBAnalyzer:
    """Analyzes InfluxDB measurements for cleaning opportunities"""

    def __init__(self, host='localhost', port=8086, username='', password='', database=''):
        self.client = InfluxDBClient(host, port, username, password, database)
        self.database = database
        self.measurements = {}

    def connect_and_verify(self) -> bool:
        """Test connection to InfluxDB"""
        try:
            databases = self.client.get_list_database()
            logger.info(f"Connected to InfluxDB. Available databases: {[db['name'] for db in databases]}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            return False

    def get_measurements(self) -> List[str]:
        """Get all measurements from the database"""
        try:
            result = self.client.query("SHOW MEASUREMENTS")
            measurements = [point['name'] for point in result.get_points()]
            logger.info(f"Found {len(measurements)} measurements")
            return measurements
        except Exception as e:
            logger.error(f"Failed to get measurements: {e}")
            return []

    def analyze_measurements_parallel(self, measurements: List[str], max_workers: int = 4) -> Dict[str, Dict]:
        """Analyze multiple measurements in parallel"""
        results = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all measurement analysis tasks
            future_to_measurement = {
                executor.submit(self.analyze_measurement_fast, measurement): measurement
                for measurement in measurements
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_measurement):
                measurement = future_to_measurement[future]
                try:
                    analysis = future.result()
                    results[measurement] = analysis
                    logger.info(f"Analyzed {measurement}: {analysis['total_points']} points")
                except Exception as e:
                    logger.error(f"Failed to analyze {measurement}: {e}")
                    results[measurement] = self._create_empty_analysis(measurement)

        return results

    def analyze_measurement_fast(self, measurement: str) -> Dict:
        """Fast analysis of a single measurement with optimized queries"""
        analysis = {
            'name': measurement,
            'total_points': 0,
            'time_range': None,
            'fields': [],
            'tags': {},
            'sample_data': [],
            'last_entry': 'No data'
        }

        try:
            # Single combined query to get count, fields, and sample data
            combined_query = f'''
            SELECT COUNT(*) FROM "{measurement}";
            SELECT * FROM "{measurement}" ORDER BY time DESC LIMIT 5;
            SELECT * FROM "{measurement}" ORDER BY time ASC LIMIT 1
            '''

            # Get basic info with one query
            basic_info = self._get_basic_measurement_info(measurement)
            analysis.update(basic_info)

            # Get sample data for time range
            sample_data = self._get_sample_data_fast(measurement)
            analysis.update(sample_data)

        except Exception as e:
            logger.error(f"Fast analysis failed for {measurement}: {e}")
            # Fallback to slow method
            return self.analyze_measurement(measurement)

        return analysis

    def _get_basic_measurement_info(self, measurement: str) -> Dict:
        """Get basic measurement info with minimal queries"""
        info = {
            'total_points': 0,
            'fields': [],
            'tags': {}
        }

        try:
            # Get count with optimized query
            count_query = f'SELECT COUNT(*) FROM "{measurement}" LIMIT 1'
            result = self.client.query(count_query)
            points = list(result.get_points())
            if points:
                info['total_points'] = sum(v for v in points[0].values() if isinstance(v, (int, float)))

            # Get field and tag info (these are metadata queries, relatively fast)
            field_result = self.client.query(f'SHOW FIELD KEYS FROM "{measurement}"')
            info['fields'] = [point['fieldKey'] for point in field_result.get_points()]

            tag_result = self.client.query(f'SHOW TAG KEYS FROM "{measurement}"')
            tag_keys = [point['tagKey'] for point in tag_result.get_points()]

            # Only get tag values if there aren't too many tags (performance optimization)
            if len(tag_keys) <= 5:  # Limit to avoid slow queries
                for tag_key in tag_keys:
                    tag_values_result = self.client.query(f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "{tag_key}" LIMIT 10')
                    info['tags'][tag_key] = [point['value'] for point in tag_values_result.get_points()]
            else:
                # Just store tag keys without values for performance
                info['tags'] = {key: [] for key in tag_keys}

        except Exception as e:
            logger.error(f"Failed to get basic info for {measurement}: {e}")

        return info

    def _get_sample_data_fast(self, measurement: str) -> Dict:
        """Get sample data and time range efficiently"""
        info = {
            'sample_data': [],
            'time_range': None,
            'last_entry': 'No data'
        }

        try:
            # Get only recent samples (faster than full scan)
            sample_query = f'SELECT * FROM "{measurement}" ORDER BY time DESC LIMIT 3'
            sample_result = self.client.query(sample_query)
            sample_points = list(sample_result.get_points())

            if sample_points:
                info['sample_data'] = sample_points

                # Get time range from samples
                times = []
                for point in sample_points:
                    try:
                        time_obj = datetime.fromisoformat(point['time'].replace('Z', '+00:00'))
                        times.append(time_obj)
                    except:
                        continue

                if times:
                    latest_time = max(times)
                    info['last_entry'] = latest_time.strftime('%Y-%m-%d %H:%M:%S')
                    info['time_range'] = {
                        'start': min(times).isoformat(),
                        'end': latest_time.isoformat()
                    }

        except Exception as e:
            logger.error(f"Failed to get sample data for {measurement}: {e}")

        return info

    def _create_empty_analysis(self, measurement: str) -> Dict:
        """Create empty analysis for failed measurements"""
        return {
            'name': measurement,
            'total_points': 0,
            'time_range': None,
            'fields': [],
            'tags': {},
            'sample_data': [],
            'last_entry': 'Error'
        }

    def analyze_measurement(self, measurement: str) -> Dict:
        """Analyze a single measurement for data quality"""
        analysis = {
            'name': measurement,
            'total_points': 0,
            'time_range': None,
            'fields': [],
            'tags': {},
            'sample_data': []
        }

        try:
            # Get total point count
            count_query = f'SELECT COUNT(*) FROM "{measurement}"'
            result = self.client.query(count_query)
            points = list(result.get_points())
            if points:
                # Sum only numeric values, skip strings like 'time'
                analysis['total_points'] = sum(v for v in points[0].values() if isinstance(v, (int, float)))

            # Get field and tag information
            field_query = f'SHOW FIELD KEYS FROM "{measurement}"'
            field_result = self.client.query(field_query)
            analysis['fields'] = [point['fieldKey'] for point in field_result.get_points()]

            tag_query = f'SHOW TAG KEYS FROM "{measurement}"'
            tag_result = self.client.query(tag_query)
            tag_keys = [point['tagKey'] for point in tag_result.get_points()]

            # Get tag values for each tag key
            for tag_key in tag_keys:
                tag_values_query = f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "{tag_key}"'
                tag_values_result = self.client.query(tag_values_query)
                analysis['tags'][tag_key] = [point['value'] for point in tag_values_result.get_points()]

            # Get time range and sample data
            sample_query = f'SELECT * FROM "{measurement}" ORDER BY time DESC LIMIT 10'
            sample_result = self.client.query(sample_query)
            sample_points = list(sample_result.get_points())

            if sample_points:
                analysis['sample_data'] = sample_points[:5]  # Keep only 5 samples
                times = [datetime.fromisoformat(point['time'].replace('Z', '+00:00')) for point in sample_points]
                analysis['time_range'] = {
                    'start': min(times).isoformat(),
                    'end': max(times).isoformat()
                }
                # Add last entry timestamp (most recent)
                analysis['last_entry'] = max(times).strftime('%Y-%m-%d %H:%M:%S')
            else:
                analysis['last_entry'] = 'No data'

        except Exception as e:
            logger.error(f"Failed to analyze measurement {measurement}: {e}")

        return analysis

    def get_problematic_measurements(self, min_points=10) -> Dict[str, List[str]]:
        """Identify measurements that might need cleaning"""
        measurements = self.get_measurements()
        problematic = {
            'low_data': [],      # Measurements with few data points
            'mixed_topics': [],  # Measurements that might contain mixed data
            'duplicates': []     # Potential duplicate measurements
        }

        measurement_analyses = []

        for measurement in measurements:
            analysis = self.analyze_measurement(measurement)
            measurement_analyses.append(analysis)

            # Check for low data count
            if analysis['total_points'] < min_points:
                problematic['low_data'].append(measurement)

            # Check for potential topic mixing (simplified heuristic)
            if len(analysis['tags']) > 3 and analysis['total_points'] > 100:
                problematic['mixed_topics'].append(measurement)

        # Check for potential duplicates (measurements with similar names)
        for i, measurement1 in enumerate(measurements):
            for measurement2 in measurements[i+1:]:
                if self._measurements_similar(measurement1, measurement2):
                    if measurement1 not in problematic['duplicates']:
                        problematic['duplicates'].append(measurement1)
                    if measurement2 not in problematic['duplicates']:
                        problematic['duplicates'].append(measurement2)

        self.measurements = {analysis['name']: analysis for analysis in measurement_analyses}
        return problematic

    def _measurements_similar(self, name1: str, name2: str) -> bool:
        """Simple heuristic to check if measurement names are similar"""
        # Remove common suffixes/prefixes and check similarity
        clean1 = name1.lower().replace('_', '').replace('-', '')
        clean2 = name2.lower().replace('_', '').replace('-', '')

        # Check if one is contained in the other or if they share significant overlap
        if len(clean1) > 3 and len(clean2) > 3:
            return clean1 in clean2 or clean2 in clean1 or \
                   len(set(clean1) & set(clean2)) / max(len(clean1), len(clean2)) > 0.7
        return False


class InfluxCleanerGUI:
    """GUI for the InfluxDB cleaner"""

    def __init__(self):
        self.analyzer = None
        self.root = tk.Tk()
        self.root.title("InfluxDB v1 Data Cleaner")
        self.root.geometry("1200x800")

        self.setup_gui()

    def setup_gui(self):
        """Setup the GUI layout"""
        # Connection frame
        conn_frame = ttk.LabelFrame(self.root, text="Database Connection", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, sticky="w")
        self.host_var = tk.StringVar(value="localhost")
        ttk.Entry(conn_frame, textvariable=self.host_var, width=15).grid(row=0, column=1, padx=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky="w")
        self.port_var = tk.StringVar(value="8086")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=10).grid(row=0, column=3, padx=5)

        ttk.Label(conn_frame, text="Database:").grid(row=0, column=4, sticky="w")
        self.db_var = tk.StringVar()
        ttk.Entry(conn_frame, textvariable=self.db_var, width=20).grid(row=0, column=5, padx=5)

        ttk.Button(conn_frame, text="Connect", command=self.connect_db).grid(row=0, column=6, padx=10)
        ttk.Button(conn_frame, text="Analyze", command=self.analyze_db).grid(row=0, column=7, padx=5)

        # Results frame
        results_frame = ttk.LabelFrame(self.root, text="Analysis Results", padding="10")
        results_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Overview tab
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Overview")

        self.overview_text = ScrolledText(self.overview_frame, width=80, height=20)
        self.overview_text.grid(row=0, column=0, sticky="nsew")

        # Measurements tab
        self.measurements_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.measurements_frame, text="Measurements")

        # Hierarchy tab
        self.hierarchy_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.hierarchy_frame, text="Hierarchy")

        # Create treeview for measurements (enable multiple selection)
        self.tree = ttk.Treeview(self.measurements_frame, columns=('Points', 'Fields', 'Tags', 'LastEntry', 'Status'), show='tree headings', selectmode='extended')
        self.tree.heading('#0', text='Measurement')
        self.tree.heading('Points', text='Data Points')
        self.tree.heading('Fields', text='Fields')
        self.tree.heading('Tags', text='Tags')
        self.tree.heading('LastEntry', text='Last Entry')
        self.tree.heading('Status', text='Status')

        # Set column widths
        self.tree.column('Points', width=80)
        self.tree.column('Fields', width=60)
        self.tree.column('Tags', width=60)
        self.tree.column('LastEntry', width=120)
        self.tree.column('Status', width=100)

        self.tree.grid(row=0, column=0, sticky="nsew")

        # Add double-click binding for measurement details
        self.tree.bind('<Double-1>', self.on_measurement_double_click)

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(self.measurements_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Setup hierarchy tree
        self.setup_hierarchy_tree()

        # Actions frame
        actions_frame = ttk.LabelFrame(self.root, text="Actions", padding="10")
        actions_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        ttk.Button(actions_frame, text="Export Analysis", command=self.export_analysis).grid(row=0, column=0, padx=5)
        ttk.Button(actions_frame, text="Delete Selected", command=self.delete_selected).grid(row=0, column=1, padx=5)
        ttk.Button(actions_frame, text="Merge Selected", command=self.merge_selected).grid(row=0, column=2, padx=5)
        ttk.Button(actions_frame, text="Clean Low Data", command=self.clean_low_data).grid(row=0, column=3, padx=5)

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        self.overview_frame.columnconfigure(0, weight=1)
        self.overview_frame.rowconfigure(0, weight=1)
        self.measurements_frame.columnconfigure(0, weight=1)
        self.measurements_frame.rowconfigure(0, weight=1)
        self.hierarchy_frame.columnconfigure(0, weight=1)
        self.hierarchy_frame.rowconfigure(0, weight=1)

    def connect_db(self):
        """Connect to the InfluxDB database"""
        try:
            self.analyzer = InfluxDBAnalyzer(
                host=self.host_var.get(),
                port=int(self.port_var.get()),
                database=self.db_var.get()
            )

            if self.analyzer.connect_and_verify():
                messagebox.showinfo("Success", "Connected to InfluxDB successfully!")
            else:
                messagebox.showerror("Error", "Failed to connect to InfluxDB")

        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {str(e)}")

    def analyze_db(self):
        """Analyze the database for cleaning opportunities with performance optimization"""
        if not self.analyzer:
            messagebox.showerror("Error", "Please connect to database first")
            return

        try:
            # Show progress
            self.show_analysis_progress("Starting analysis...")

            # Use optimized parallel analysis
            measurements = self.analyzer.get_measurements()
            if not measurements:
                messagebox.showinfo("Info", "No measurements found in database")
                return

            self.show_analysis_progress(f"Analyzing {len(measurements)} measurements in parallel...")

            # Use parallel analysis for better performance
            self.analyzer.measurements = self.analyzer.analyze_measurements_parallel(measurements)

            self.show_analysis_progress("Identifying problematic measurements...")
            problematic = self.analyzer.get_problematic_measurements()

            # Update overview
            overview = f"Analysis Results:\n\n"
            overview += f"Total measurements: {len(self.analyzer.measurements)}\n"
            overview += f"Low data measurements: {len(problematic['low_data'])}\n"
            overview += f"Mixed topic measurements: {len(problematic['mixed_topics'])}\n"
            overview += f"Potential duplicates: {len(problematic['duplicates'])}\n\n"

            overview += "Low data measurements:\n"
            for measurement in problematic['low_data']:
                points = self.analyzer.measurements[measurement]['total_points']
                overview += f"  - {measurement}: {points} points\n"

            overview += "\nMixed topic measurements:\n"
            for measurement in problematic['mixed_topics']:
                tags = len(self.analyzer.measurements[measurement]['tags'])
                overview += f"  - {measurement}: {tags} tag keys\n"

            overview += "\nPotential duplicates:\n"
            for measurement in problematic['duplicates']:
                overview += f"  - {measurement}\n"

            self.overview_text.delete(1.0, tk.END)
            self.overview_text.insert(1.0, overview)

            # Update measurements tree
            self.tree.delete(*self.tree.get_children())

            for name, analysis in self.analyzer.measurements.items():
                status = "OK"
                if name in problematic['low_data']:
                    status = "Low Data"
                elif name in problematic['mixed_topics']:
                    status = "Mixed Topics"
                elif name in problematic['duplicates']:
                    status = "Potential Duplicate"

                self.tree.insert('', 'end', text=name, values=(
                    analysis['total_points'],
                    len(analysis['fields']),
                    len(analysis['tags']),
                    analysis.get('last_entry', 'Unknown'),
                    status
                ))

            self.show_analysis_progress("Building hierarchy tree...")
            # Update hierarchy tree
            self.populate_hierarchy_tree()

            self.show_analysis_progress("Analysis complete!", final=True)

        except Exception as e:
            self.show_analysis_progress("Analysis failed!", final=True)
            messagebox.showerror("Error", f"Analysis failed: {str(e)}")

    def show_analysis_progress(self, message: str, final: bool = False):
        """Show analysis progress to user"""
        self.overview_text.delete(1.0, tk.END)
        if final:
            self.overview_text.insert(1.0, f"✅ {message}\n\nAnalysis completed successfully!")
        else:
            self.overview_text.insert(1.0, f"⏳ {message}\n\nPlease wait...")

        # Force UI update
        self.root.update_idletasks()
        self.root.update()

    def export_analysis(self):
        """Export analysis results to JSON file"""
        if not self.analyzer or not self.analyzer.measurements:
            messagebox.showerror("Error", "No analysis data to export")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.analyzer.measurements, f, indent=2, default=str)
                messagebox.showinfo("Success", f"Analysis exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")

    def setup_hierarchy_tree(self):
        """Setup the hierarchy tree widget"""
        # Create hierarchy tree with columns
        self.hierarchy_tree = ttk.Treeview(self.hierarchy_frame, columns=('Count', 'Points', 'LastEntry'), show='tree headings')
        self.hierarchy_tree.heading('#0', text='Measurement Hierarchy')
        self.hierarchy_tree.heading('Count', text='Count')
        self.hierarchy_tree.heading('Points', text='Total Points')
        self.hierarchy_tree.heading('LastEntry', text='Latest Entry')

        # Set column widths
        self.hierarchy_tree.column('Count', width=60)
        self.hierarchy_tree.column('Points', width=80)
        self.hierarchy_tree.column('LastEntry', width=120)

        self.hierarchy_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar for hierarchy tree
        hierarchy_scrollbar = ttk.Scrollbar(self.hierarchy_frame, orient="vertical", command=self.hierarchy_tree.yview)
        self.hierarchy_tree.configure(yscrollcommand=hierarchy_scrollbar.set)
        hierarchy_scrollbar.grid(row=0, column=1, sticky="ns")

        # Add double-click binding
        self.hierarchy_tree.bind('<Double-1>', self.on_hierarchy_double_click)

    def build_measurement_hierarchy(self) -> Dict:
        """Build a hierarchical structure of measurements"""
        if not self.analyzer or not self.analyzer.measurements:
            return {}

        hierarchy = {}
        measurements = self.analyzer.measurements

        # Group by common prefixes (split by underscore, dot, dash)
        for name, analysis in measurements.items():
            parts = self._split_measurement_name(name)
            current_level = hierarchy

            # Build tree structure
            for i, part in enumerate(parts):
                if part not in current_level:
                    current_level[part] = {
                        '_children': {},
                        '_measurements': [],
                        '_stats': {
                            'count': 0,
                            'total_points': 0,
                            'latest_entry': None
                        }
                    }

                current_level[part]['_stats']['count'] += 1
                current_level[part]['_stats']['total_points'] += analysis.get('total_points', 0)

                # Update latest entry
                entry_time = analysis.get('last_entry', '')
                if entry_time and entry_time != 'No data':
                    current_latest = current_level[part]['_stats']['latest_entry']
                    if not current_latest or entry_time > current_latest:
                        current_level[part]['_stats']['latest_entry'] = entry_time

                # If this is the last part, add the full measurement
                if i == len(parts) - 1:
                    current_level[part]['_measurements'].append({
                        'name': name,
                        'analysis': analysis
                    })
                else:
                    current_level = current_level[part]['_children']

        # Also group by tags if available
        tag_hierarchy = self._group_by_tags(measurements)
        if tag_hierarchy:
            hierarchy['[By Tags]'] = tag_hierarchy

        # Group by topic/domain (heuristic based on common patterns)
        topic_hierarchy = self._group_by_topics(measurements)
        if topic_hierarchy:
            hierarchy['[By Topics]'] = topic_hierarchy

        return hierarchy

    def _split_measurement_name(self, name: str) -> List[str]:
        """Split measurement name into logical parts"""
        # Replace common separators with underscores, then split
        import re
        normalized = re.sub(r'[._\-/]', '_', name)
        parts = [part for part in normalized.split('_') if part]

        # If no separators found, try camelCase/PascalCase splitting
        if len(parts) == 1:
            camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+|[0-9]+', name)
            if len(camel_parts) > 1:
                parts = camel_parts

        return parts if len(parts) > 1 else [name]

    def _group_by_tags(self, measurements: Dict) -> Dict:
        """Group measurements by common tags"""
        tag_groups = {}

        for name, analysis in measurements.items():
            tags = analysis.get('tags', {})

            if not tags:
                continue

            # Group by each tag key
            for tag_key, tag_values in tags.items():
                if tag_key not in tag_groups:
                    tag_groups[tag_key] = {
                        '_children': {},
                        '_measurements': [],
                        '_stats': {'count': 0, 'total_points': 0, 'latest_entry': None}
                    }

                # Group by tag values
                for tag_value in tag_values:
                    if tag_value not in tag_groups[tag_key]['_children']:
                        tag_groups[tag_key]['_children'][tag_value] = {
                            '_children': {},
                            '_measurements': [],
                            '_stats': {'count': 0, 'total_points': 0, 'latest_entry': None}
                        }

                    # Add measurement to this tag value group
                    tag_groups[tag_key]['_children'][tag_value]['_measurements'].append({
                        'name': name,
                        'analysis': analysis
                    })

                    # Update stats
                    tag_groups[tag_key]['_children'][tag_value]['_stats']['count'] += 1
                    tag_groups[tag_key]['_children'][tag_value]['_stats']['total_points'] += analysis.get('total_points', 0)

                    entry_time = analysis.get('last_entry', '')
                    if entry_time and entry_time != 'No data':
                        current_latest = tag_groups[tag_key]['_children'][tag_value]['_stats']['latest_entry']
                        if not current_latest or entry_time > current_latest:
                            tag_groups[tag_key]['_children'][tag_value]['_stats']['latest_entry'] = entry_time

                # Update parent stats
                tag_groups[tag_key]['_stats']['count'] += 1
                tag_groups[tag_key]['_stats']['total_points'] += analysis.get('total_points', 0)

        return tag_groups

    def _group_by_topics(self, measurements: Dict) -> Dict:
        """Group measurements by inferred topics"""
        topics = {
            'sensor': ['temp', 'temperature', 'humid', 'pressure', 'light', 'motion', 'distance'],
            'system': ['cpu', 'memory', 'disk', 'network', 'load', 'uptime'],
            'power': ['voltage', 'current', 'power', 'battery', 'energy'],
            'weather': ['weather', 'wind', 'rain', 'sun', 'cloud'],
            'home': ['home', 'room', 'kitchen', 'living', 'bedroom', 'garage'],
            'vehicle': ['car', 'truck', 'vehicle', 'engine', 'fuel', 'speed'],
            'industrial': ['machine', 'production', 'factory', 'pump', 'motor']
        }

        topic_groups = {}

        for name, analysis in measurements.items():
            name_lower = name.lower()
            matched_topics = []

            # Check which topics match
            for topic, keywords in topics.items():
                if any(keyword in name_lower for keyword in keywords):
                    matched_topics.append(topic)

            # If no topic matches, use 'other'
            if not matched_topics:
                matched_topics = ['other']

            # Add to each matching topic
            for topic in matched_topics:
                if topic not in topic_groups:
                    topic_groups[topic] = {
                        '_children': {},
                        '_measurements': [],
                        '_stats': {'count': 0, 'total_points': 0, 'latest_entry': None}
                    }

                topic_groups[topic]['_measurements'].append({
                    'name': name,
                    'analysis': analysis
                })

                # Update stats
                topic_groups[topic]['_stats']['count'] += 1
                topic_groups[topic]['_stats']['total_points'] += analysis.get('total_points', 0)

                entry_time = analysis.get('last_entry', '')
                if entry_time and entry_time != 'No data':
                    current_latest = topic_groups[topic]['_stats']['latest_entry']
                    if not current_latest or entry_time > current_latest:
                        topic_groups[topic]['_stats']['latest_entry'] = entry_time

        return topic_groups

    def populate_hierarchy_tree(self):
        """Populate the hierarchy tree with measurement data"""
        if not hasattr(self, 'hierarchy_tree'):
            return

        # Clear existing items
        self.hierarchy_tree.delete(*self.hierarchy_tree.get_children())

        # Build hierarchy
        hierarchy = self.build_measurement_hierarchy()

        if not hierarchy:
            return

        # Populate tree
        self._add_hierarchy_nodes('', hierarchy)

        # Expand first level
        for item in self.hierarchy_tree.get_children():
            self.hierarchy_tree.item(item, open=True)

    def _add_hierarchy_nodes(self, parent: str, nodes: Dict):
        """Recursively add nodes to the hierarchy tree"""
        for name, data in nodes.items():
            if name.startswith('_'):  # Skip metadata keys
                continue

            stats = data.get('_stats', {})
            count = stats.get('count', 0)
            total_points = stats.get('total_points', 0)
            latest_entry = stats.get('latest_entry', 'No data')

            # Add node
            node_id = self.hierarchy_tree.insert(parent, 'end', text=name, values=(count, total_points, latest_entry))

            # Add children
            children = data.get('_children', {})
            if children:
                self._add_hierarchy_nodes(node_id, children)

            # Add individual measurements
            measurements = data.get('_measurements', [])
            for measurement in measurements:
                m_name = measurement['name']
                m_analysis = measurement['analysis']
                self.hierarchy_tree.insert(node_id, 'end', text=f"📊 {m_name}",
                    values=(1, m_analysis.get('total_points', 0), m_analysis.get('last_entry', 'No data')))

    def on_hierarchy_double_click(self, event):
        """Handle double-click on hierarchy item"""
        selected_item = self.hierarchy_tree.selection()
        if not selected_item:
            return

        item = selected_item[0]
        item_text = self.hierarchy_tree.item(item, 'text')

        # If it's a measurement (starts with 📊), show details
        if item_text.startswith('📊 '):
            measurement_name = item_text[2:]  # Remove emoji prefix
            if measurement_name in self.analyzer.measurements:
                analysis = self.analyzer.measurements[measurement_name]
                details = f"Measurement: {measurement_name}\n\n"
                details += f"Total Points: {analysis['total_points']}\n"
                details += f"Fields: {', '.join(analysis['fields'])}\n"
                details += f"Tags: {list(analysis['tags'].keys())}\n"
                details += f"Time Range: {analysis.get('time_range', 'Unknown')}\n\n"
                details += "Sample Data:\n"
                for sample in analysis['sample_data'][:3]:
                    details += f"  {sample}\n"

                messagebox.showinfo(f"Details: {measurement_name}", details)

    def get_selected_measurements(self):
        """Get list of selected measurements from treeview"""
        selected_items = self.tree.selection()
        selected_measurements = []
        for item in selected_items:
            measurement_name = self.tree.item(item, 'text')
            selected_measurements.append(measurement_name)
        return selected_measurements

    def on_measurement_double_click(self, event):
        """Handle double-click on measurement for details"""
        selected = self.get_selected_measurements()
        if selected:
            measurement = selected[0]
            if measurement in self.analyzer.measurements:
                analysis = self.analyzer.measurements[measurement]
                details = f"Measurement: {measurement}\n\n"
                details += f"Total Points: {analysis['total_points']}\n"
                details += f"Fields: {', '.join(analysis['fields'])}\n"
                details += f"Tags: {list(analysis['tags'].keys())}\n"
                details += f"Time Range: {analysis.get('time_range', 'Unknown')}\n\n"
                details += "Sample Data:\n"
                for sample in analysis['sample_data'][:3]:
                    details += f"  {sample}\n"

                messagebox.showinfo(f"Details: {measurement}", details)

    def delete_selected(self):
        """Delete selected measurements with confirmation"""
        selected = self.get_selected_measurements()

        if not selected:
            messagebox.showwarning("No Selection", "Please select measurements to delete.")
            return

        if not self.analyzer:
            messagebox.showerror("Error", "Please connect to database first")
            return

        # Show confirmation dialog
        measurement_list = "\n".join([f"• {m}" for m in selected])
        confirm_message = f"Are you sure you want to DELETE the following measurements?\n\n{measurement_list}\n\nThis action cannot be undone!\n\nBackups will be created automatically."

        if messagebox.askyesno("Confirm Deletion", confirm_message):
            try:
                # Import the cleaner core
                from cleaner_core import InfluxDBCleaner
                cleaner = InfluxDBCleaner(self.analyzer.client, self.analyzer.database)

                results = {}
                for measurement in selected:
                    # Backup first, then delete
                    backup_success = cleaner.backup_measurement(measurement)
                    if backup_success:
                        delete_success = cleaner.delete_measurement(measurement, confirm=True)
                        results[measurement] = delete_success
                    else:
                        results[measurement] = False
                        messagebox.showerror("Error", f"Failed to backup {measurement}. Deletion cancelled for safety.")
                        break

                # Show results
                successful = [m for m, success in results.items() if success]
                failed = [m for m, success in results.items() if not success]

                result_message = f"Deletion Results:\n\nSuccessful: {len(successful)}\nFailed: {len(failed)}"
                if successful:
                    result_message += f"\n\nDeleted:\n" + "\n".join([f"• {m}" for m in successful])
                if failed:
                    result_message += f"\n\nFailed:\n" + "\n".join([f"• {m}" for m in failed])

                messagebox.showinfo("Deletion Complete", result_message)

                # Refresh analysis
                self.analyze_db()

            except Exception as e:
                messagebox.showerror("Error", f"Deletion failed: {str(e)}")

    def merge_selected(self):
        """Merge selected measurements with confirmation"""
        selected = self.get_selected_measurements()

        if len(selected) < 2:
            messagebox.showwarning("Insufficient Selection", "Please select at least 2 measurements to merge.")
            return

        if not self.analyzer:
            messagebox.showerror("Error", "Please connect to database first")
            return

        # Ask for target measurement name
        target_name = tk.simpledialog.askstring("Target Measurement",
            f"Enter name for the merged measurement:\n\nMerging {len(selected)} measurements:\n" +
            "\n".join([f"• {m}" for m in selected]))

        if not target_name:
            return

        # Show confirmation dialog
        measurement_list = "\n".join([f"• {m}" for m in selected])
        confirm_message = f"Are you sure you want to MERGE the following measurements into '{target_name}'?\n\n{measurement_list}\n\nOriginal measurements will be kept as backups.\nSource measurement info will be added as tags."

        if messagebox.askyesno("Confirm Merge", confirm_message):
            try:
                # Import the cleaner core
                from cleaner_core import InfluxDBCleaner
                cleaner = InfluxDBCleaner(self.analyzer.client, self.analyzer.database)

                # Perform merge
                success = cleaner.merge_measurements(selected, target_name)

                if success:
                    messagebox.showinfo("Merge Complete", f"Successfully merged {len(selected)} measurements into '{target_name}'")
                    # Refresh analysis
                    self.analyze_db()
                else:
                    messagebox.showerror("Error", "Merge operation failed. Check logs for details.")

            except Exception as e:
                messagebox.showerror("Error", f"Merge failed: {str(e)}")

    def clean_low_data(self):
        """Clean measurements with low data points"""
        if not self.analyzer:
            messagebox.showerror("Error", "Please connect to database first")
            return

        min_points = tk.simpledialog.askinteger("Minimum Points",
            "Enter minimum number of data points (measurements with fewer points will be cleaned):",
            initialvalue=10, minvalue=1)

        if min_points is None:
            return

        # Find measurements with low data
        low_data_measurements = []
        for name, analysis in self.analyzer.measurements.items():
            if analysis['total_points'] < min_points:
                low_data_measurements.append(f"{name} ({analysis['total_points']} points)")

        if not low_data_measurements:
            messagebox.showinfo("No Action Needed", f"No measurements found with fewer than {min_points} points.")
            return

        # Show confirmation
        measurement_list = "\n".join([f"• {m}" for m in low_data_measurements])
        confirm_message = f"Found {len(low_data_measurements)} measurements with fewer than {min_points} points:\n\n{measurement_list}\n\nDelete these measurements?\nBackups will be created automatically."

        if messagebox.askyesno("Confirm Low Data Cleanup", confirm_message):
            try:
                from cleaner_core import InfluxDBCleaner
                cleaner = InfluxDBCleaner(self.analyzer.client, self.analyzer.database)

                results = cleaner.clean_low_data_measurements(min_points, action='delete')

                successful = sum(1 for success in results.values() if success)
                total = len(results)

                messagebox.showinfo("Cleanup Complete", f"Successfully cleaned {successful}/{total} measurements.")

                # Refresh analysis
                self.analyze_db()

            except Exception as e:
                messagebox.showerror("Error", f"Cleanup failed: {str(e)}")

    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='InfluxDB v1 Data Cleaner')
    parser.add_argument('--host', default='localhost', help='InfluxDB host')
    parser.add_argument('--port', type=int, default=8086, help='InfluxDB port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI')

    args = parser.parse_args()

    if args.no_gui:
        # Command line mode
        analyzer = InfluxDBAnalyzer(args.host, args.port, database=args.database)
        if analyzer.connect_and_verify():
            problematic = analyzer.get_problematic_measurements()
            print(json.dumps(problematic, indent=2))
    else:
        # GUI mode
        app = InfluxCleanerGUI()
        app.run()


if __name__ == "__main__":
    main()