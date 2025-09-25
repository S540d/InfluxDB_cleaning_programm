#!/usr/bin/env python3
"""
Core cleaning functionality for InfluxDB v1 Data Cleaner

This module provides the actual data manipulation and cleaning operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from influxdb import InfluxDBClient
import json
import re

logger = logging.getLogger(__name__)


class InfluxDBCleaner:
    """Handles the actual data cleaning operations"""

    def __init__(self, client: InfluxDBClient, database: str):
        self.client = client
        self.database = database

    def backup_measurement(self, measurement: str, backup_file: str = None) -> bool:
        """Create a backup of a measurement before cleaning"""
        try:
            if backup_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{measurement}_backup_{timestamp}.json"

            # Query all data from the measurement
            query = f'SELECT * FROM "{measurement}"'
            result = self.client.query(query)

            # Convert to list and save as JSON
            data = list(result.get_points())

            with open(backup_file, 'w') as f:
                json.dump({
                    'measurement': measurement,
                    'backup_time': datetime.now().isoformat(),
                    'data_points': len(data),
                    'data': data
                }, f, indent=2, default=str)

            logger.info(f"Backed up {len(data)} points from {measurement} to {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to backup measurement {measurement}: {e}")
            return False

    def delete_measurement(self, measurement: str, confirm: bool = False) -> bool:
        """Delete a measurement completely"""
        if not confirm:
            logger.warning("Delete operation requires confirmation")
            return False

        try:
            query = f'DROP MEASUREMENT "{measurement}"'
            self.client.query(query)
            logger.info(f"Deleted measurement: {measurement}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete measurement {measurement}: {e}")
            return False

    def merge_measurements(self, source_measurements: List[str], target_measurement: str,
                          tag_mapping: Dict[str, str] = None) -> bool:
        """Merge multiple measurements into a single target measurement"""

        if not source_measurements:
            logger.warning("No source measurements provided")
            return False

        try:
            total_points = 0

            for source in source_measurements:
                # Get all data from source measurement
                query = f'SELECT * FROM "{source}"'
                result = self.client.query(query)
                points = list(result.get_points())

                if not points:
                    logger.warning(f"No data found in measurement {source}")
                    continue

                # Prepare data for insertion
                new_points = []
                for point in points:
                    new_point = {
                        'measurement': target_measurement,
                        'time': point.get('time'),
                        'fields': {},
                        'tags': {}
                    }

                    # Copy fields (exclude 'time' from fields)
                    for key, value in point.items():
                        if key not in ['time'] and not key.startswith('tag_'):
                            new_point['fields'][key] = value

                    # Apply tag mapping if provided
                    if tag_mapping:
                        for old_tag, new_tag in tag_mapping.items():
                            if old_tag in point:
                                new_point['tags'][new_tag] = point[old_tag]

                    # Add source information as tag
                    new_point['tags']['source_measurement'] = source

                    new_points.append(new_point)

                # Write merged data to target measurement
                if new_points:
                    self.client.write_points(new_points)
                    total_points += len(new_points)
                    logger.info(f"Merged {len(new_points)} points from {source} to {target_measurement}")

            logger.info(f"Successfully merged {total_points} total points into {target_measurement}")
            return True

        except Exception as e:
            logger.error(f"Failed to merge measurements: {e}")
            return False

    def consolidate_by_pattern(self, pattern: str, target_measurement: str) -> bool:
        """Consolidate measurements matching a pattern into a single measurement"""
        try:
            # Get all measurements
            result = self.client.query("SHOW MEASUREMENTS")
            all_measurements = [point['name'] for point in result.get_points()]

            # Find measurements matching pattern
            matching = [m for m in all_measurements if pattern.lower() in m.lower()]

            if not matching:
                logger.warning(f"No measurements found matching pattern: {pattern}")
                return False

            logger.info(f"Found {len(matching)} measurements matching pattern '{pattern}': {matching}")

            # Merge all matching measurements
            return self.merge_measurements(matching, target_measurement)

        except Exception as e:
            logger.error(f"Failed to consolidate by pattern {pattern}: {e}")
            return False

    def clean_low_data_measurements(self, min_points: int = 10, action: str = 'delete') -> Dict[str, bool]:
        """Clean measurements with low data points"""
        results = {}

        try:
            # Get all measurements
            result = self.client.query("SHOW MEASUREMENTS")
            measurements = [point['name'] for point in result.get_points()]

            for measurement in measurements:
                # Count points in measurement
                count_query = f'SELECT COUNT(*) FROM "{measurement}"'
                count_result = self.client.query(count_query)
                points = list(count_result.get_points())

                if points:
                    total_points = sum(points[0].values())

                    if total_points < min_points:
                        logger.info(f"Measurement {measurement} has only {total_points} points")

                        if action == 'delete':
                            # Backup first
                            backup_success = self.backup_measurement(measurement)
                            if backup_success:
                                results[measurement] = self.delete_measurement(measurement, confirm=True)
                            else:
                                results[measurement] = False
                                logger.error(f"Skipping deletion of {measurement} due to backup failure")

                        elif action == 'backup_only':
                            results[measurement] = self.backup_measurement(measurement)

        except Exception as e:
            logger.error(f"Failed to clean low data measurements: {e}")

        return results

    def split_measurement_by_tag(self, measurement: str, tag_key: str) -> Dict[str, bool]:
        """Split a measurement into multiple measurements based on tag values"""
        results = {}

        try:
            # Get all unique values for the specified tag
            tag_query = f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "{tag_key}"'
            tag_result = self.client.query(tag_query)
            tag_values = [point['value'] for point in tag_result.get_points()]

            if not tag_values:
                logger.warning(f"No tag values found for {tag_key} in {measurement}")
                return results

            logger.info(f"Splitting {measurement} by {tag_key} into {len(tag_values)} measurements")

            for tag_value in tag_values:
                new_measurement_name = f"{measurement}_{tag_value}"

                # Query data for this specific tag value
                data_query = f'SELECT * FROM "{measurement}" WHERE "{tag_key}" = \'{tag_value}\''
                data_result = self.client.query(data_query)
                points = list(data_result.get_points())

                if points:
                    # Prepare points for new measurement
                    new_points = []
                    for point in points:
                        new_point = {
                            'measurement': new_measurement_name,
                            'time': point.get('time'),
                            'fields': {},
                            'tags': {}
                        }

                        # Copy fields and tags, excluding the split tag
                        for key, value in point.items():
                            if key == 'time':
                                continue
                            elif key == tag_key:
                                continue  # Don't include the split tag
                            elif not key.startswith('tag_'):
                                new_point['fields'][key] = value
                            else:
                                new_point['tags'][key] = value

                        # Add original measurement as source tag
                        new_point['tags']['source_measurement'] = measurement

                        new_points.append(new_point)

                    # Write new measurement
                    self.client.write_points(new_points)
                    results[new_measurement_name] = True
                    logger.info(f"Created {new_measurement_name} with {len(new_points)} points")
                else:
                    results[new_measurement_name] = False
                    logger.warning(f"No data found for {tag_key}={tag_value}")

        except Exception as e:
            logger.error(f"Failed to split measurement {measurement}: {e}")

        return results

    def rename_measurement(self, old_name: str, new_name: str) -> bool:
        """Rename a measurement by copying data to new measurement and deleting old one"""
        try:
            # First backup the measurement
            backup_success = self.backup_measurement(old_name)
            if not backup_success:
                logger.error(f"Failed to backup {old_name}, aborting rename")
                return False

            # Copy data to new measurement
            query = f'SELECT * FROM "{old_name}"'
            result = self.client.query(query)
            points = list(result.get_points())

            if not points:
                logger.warning(f"No data found in {old_name}")
                return False

            # Prepare data for new measurement
            new_points = []
            for point in points:
                new_point = {
                    'measurement': new_name,
                    'time': point.get('time'),
                    'fields': {},
                    'tags': {}
                }

                # Copy fields and tags
                for key, value in point.items():
                    if key == 'time':
                        continue
                    elif not key.startswith('tag_'):
                        new_point['fields'][key] = value
                    else:
                        new_point['tags'][key] = value

                new_points.append(new_point)

            # Write to new measurement
            self.client.write_points(new_points)
            logger.info(f"Created new measurement {new_name} with {len(new_points)} points")

            # Delete old measurement
            delete_success = self.delete_measurement(old_name, confirm=True)

            if delete_success:
                logger.info(f"Successfully renamed {old_name} to {new_name}")
                return True
            else:
                logger.error(f"Failed to delete old measurement {old_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to rename measurement {old_name} to {new_name}: {e}")
            return False

    def aggregate_old_data(self, measurement: str, cutoff_date: datetime,
                          aggregation: str = 'daily', fields: List[str] = None) -> bool:
        """Aggregate old data points to reduce storage while preserving trends"""
        try:
            # Backup first
            backup_success = self.backup_measurement(measurement)
            if not backup_success:
                logger.error(f"Failed to backup {measurement}, aborting aggregation")
                return False

            # Get fields if not specified
            if not fields:
                field_query = f'SHOW FIELD KEYS FROM "{measurement}"'
                field_result = self.client.query(field_query)
                fields = [point['fieldKey'] for point in field_result.get_points()]

            if not fields:
                logger.warning(f"No fields found for {measurement}")
                return False

            # Define aggregation intervals
            intervals = {
                'hourly': '1h',
                'daily': '1d',
                'weekly': '1w',
                'monthly': '30d'
            }

            if aggregation not in intervals:
                logger.error(f"Invalid aggregation type: {aggregation}")
                return False

            interval = intervals[aggregation]
            cutoff_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')

            logger.info(f"Aggregating {measurement} data older than {cutoff_str} to {aggregation} averages")

            # Create aggregated measurement name
            aggregated_name = f"{measurement}_agg_{aggregation}"

            # Build aggregation query for old data
            field_aggregations = []
            for field in fields:
                # Try different aggregation functions based on field name
                if any(keyword in field.lower() for keyword in ['count', 'total', 'sum']):
                    field_aggregations.append(f'SUM("{field}") AS "{field}"')
                elif any(keyword in field.lower() for keyword in ['max', 'peak', 'highest']):
                    field_aggregations.append(f'MAX("{field}") AS "{field}"')
                elif any(keyword in field.lower() for keyword in ['min', 'lowest']):
                    field_aggregations.append(f'MIN("{field}") AS "{field}"')
                else:
                    # Default to mean for most metrics like CPU, temperature, etc.
                    field_aggregations.append(f'MEAN("{field}") AS "{field}"')

            aggregation_fields = ', '.join(field_aggregations)

            # Query to create aggregated data
            agg_query = f'''
            SELECT {aggregation_fields}
            INTO "{aggregated_name}"
            FROM "{measurement}"
            WHERE time < '{cutoff_str}'
            GROUP BY time({interval}), *
            '''

            logger.info(f"Running aggregation query: {agg_query[:100]}...")
            result = self.client.query(agg_query)

            # Count aggregated points
            count_result = self.client.query(f'SELECT COUNT(*) FROM "{aggregated_name}"')
            aggregated_count = 0
            for point in count_result.get_points():
                aggregated_count += sum(v for v in point.values() if isinstance(v, (int, float)))

            if aggregated_count > 0:
                logger.info(f"Created {aggregated_count} aggregated data points")

                # Delete original old data
                delete_query = f'DELETE FROM "{measurement}" WHERE time < \'{cutoff_str}\''
                self.client.query(delete_query)

                logger.info(f"Successfully aggregated old data for {measurement}")
                return True
            else:
                logger.warning(f"No data was aggregated for {measurement}")
                return False

        except Exception as e:
            logger.error(f"Failed to aggregate data for {measurement}: {e}")
            return False

    def filter_and_clean_by_age(self, measurements: List[str],
                               older_than_years: float = 2.0,
                               action: str = 'aggregate') -> Dict[str, bool]:
        """Filter and clean measurements based on data age"""
        results = {}
        cutoff_date = datetime.now() - timedelta(days=older_than_years * 365)

        logger.info(f"Processing measurements with data older than {cutoff_date.strftime('%Y-%m-%d')}")

        for measurement in measurements:
            try:
                # Check if measurement has old data
                old_data_query = f'SELECT COUNT(*) FROM "{measurement}" WHERE time < \'{cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")}\''
                old_data_result = self.client.query(old_data_query)

                old_count = 0
                for point in old_data_result.get_points():
                    old_count += sum(v for v in point.values() if isinstance(v, (int, float)))

                if old_count == 0:
                    logger.info(f"No old data found in {measurement}")
                    results[measurement] = True
                    continue

                logger.info(f"Found {old_count} old data points in {measurement}")

                if action == 'aggregate':
                    # Determine best aggregation based on data density
                    if old_count > 50000:  # Very high density - monthly
                        aggregation = 'monthly'
                    elif old_count > 10000:  # High density - weekly
                        aggregation = 'weekly'
                    elif old_count > 1000:   # Medium density - daily
                        aggregation = 'daily'
                    else:                    # Low density - hourly
                        aggregation = 'hourly'

                    results[measurement] = self.aggregate_old_data(measurement, cutoff_date, aggregation)

                elif action == 'delete':
                    # Backup then delete old data
                    backup_success = self.backup_measurement(measurement)
                    if backup_success:
                        delete_query = f'DELETE FROM "{measurement}" WHERE time < \'{cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")}\''
                        self.client.query(delete_query)
                        results[measurement] = True
                        logger.info(f"Deleted old data from {measurement}")
                    else:
                        results[measurement] = False

                else:
                    logger.error(f"Invalid action: {action}")
                    results[measurement] = False

            except Exception as e:
                logger.error(f"Failed to process {measurement}: {e}")
                results[measurement] = False

        return results

    def analyze_data_density(self, measurement: str, days_back: int = 30) -> Dict:
        """Analyze data density to recommend optimal aggregation strategy"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)

            # Count total points in time window
            count_query = f'''
            SELECT COUNT(*) FROM "{measurement}"
            WHERE time >= '{start_time.strftime("%Y-%m-%dT%H:%M:%SZ")}'
            AND time <= '{end_time.strftime("%Y-%m-%dT%H:%M:%SZ")}'
            '''

            count_result = self.client.query(count_query)
            total_points = 0
            for point in count_result.get_points():
                total_points += sum(v for v in point.values() if isinstance(v, (int, float)))

            if total_points == 0:
                return {'error': 'No data in specified time range'}

            # Calculate metrics
            points_per_day = total_points / days_back
            points_per_hour = points_per_day / 24
            points_per_minute = points_per_hour / 60

            # Recommend aggregation strategy
            recommendations = []

            if points_per_minute > 10:
                recommendations.append(f"Very high frequency ({points_per_minute:.1f} points/min) - Consider hourly aggregation for old data")
            elif points_per_hour > 10:
                recommendations.append(f"High frequency ({points_per_hour:.1f} points/hour) - Consider daily aggregation for old data")
            elif points_per_day > 5:
                recommendations.append(f"Medium frequency ({points_per_day:.1f} points/day) - Consider weekly aggregation for very old data")
            else:
                recommendations.append(f"Low frequency ({points_per_day:.1f} points/day) - Aggregation may not be beneficial")

            # Estimate storage savings
            old_data_query = f'SELECT COUNT(*) FROM "{measurement}" WHERE time < \'{(end_time - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")}\''
            old_data_result = self.client.query(old_data_query)

            old_points = 0
            for point in old_data_result.get_points():
                old_points += sum(v for v in point.values() if isinstance(v, (int, float)))

            # Estimate reduction ratios
            daily_reduction = max(1, old_points / 365) if old_points > 0 else 0
            weekly_reduction = max(1, old_points / 52) if old_points > 0 else 0
            monthly_reduction = max(1, old_points / 12) if old_points > 0 else 0

            return {
                'measurement': measurement,
                'analysis_period_days': days_back,
                'total_points_analyzed': total_points,
                'points_per_minute': round(points_per_minute, 2),
                'points_per_hour': round(points_per_hour, 2),
                'points_per_day': round(points_per_day, 2),
                'old_data_points': old_points,
                'recommendations': recommendations,
                'estimated_reductions': {
                    'daily_aggregation': f"{old_points} → {int(daily_reduction)} points ({(1-daily_reduction/max(old_points,1))*100:.1f}% reduction)" if old_points > 0 else "No old data",
                    'weekly_aggregation': f"{old_points} → {int(weekly_reduction)} points ({(1-weekly_reduction/max(old_points,1))*100:.1f}% reduction)" if old_points > 0 else "No old data",
                    'monthly_aggregation': f"{old_points} → {int(monthly_reduction)} points ({(1-monthly_reduction/max(old_points,1))*100:.1f}% reduction)" if old_points > 0 else "No old data"
                }
            }

        except Exception as e:
            logger.error(f"Failed to analyze data density for {measurement}: {e}")
            return {'error': str(e)}