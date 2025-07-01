"""
Historical Analysis Module for AWS Cloud Discovery
Uses AWS CloudTrail to analyze resource growth trends and predict future Management Token requirements.
"""

import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CloudTrailAnalyzer:
    """Analyzes AWS CloudTrail events to understand resource growth patterns."""
    
    def __init__(self, regions: List[str] = None):
        self.regions = regions or ['us-east-1']
        self.cloudtrail_client = boto3.client('cloudtrail')
        self.ec2_clients = {region: boto3.client('ec2', region_name=region) for region in self.regions}
        self.elb_clients = {region: boto3.client('elbv2', region_name=region) for region in self.regions}
        
    def get_resource_events(self, days_back: int = 90) -> Dict[str, List[Dict]]:
        """
        Fetch CloudTrail events for resource creation/deletion over the specified period.
        
        Args:
            days_back: Number of days to look back for historical data
            
        Returns:
            Dictionary with resource events by type
        """
        logger.info(f"Fetching CloudTrail events for the last {days_back} days...")
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        # Events to track for Management Token calculation
        event_names = [
            'RunInstances', 'TerminateInstances',  # EC2 instances
            'CreateVpc', 'DeleteVpc',              # VPCs
            'CreateSubnet', 'DeleteSubnet',        # Subnets
            'CreateLoadBalancer', 'DeleteLoadBalancer'  # Load balancers
        ]
        
        resource_events = {
            'ec2_instances': [],
            'vpcs': [],
            'subnets': [],
            'load_balancers': []
        }
        
        for event_name in event_names:
            try:
                response = self.cloudtrail_client.lookup_events(
                    StartTime=start_time,
                    EndTime=end_time,
                    LookupAttributes=[
                        {
                            'AttributeKey': 'EventName',
                            'AttributeValue': event_name
                        }
                    ],
                    MaxResults=50  # Adjust as needed
                )
                
                for event in response.get('Events', []):
                    event_time = event['EventTime']
                    event_data = {
                        'timestamp': event_time,
                        'event_name': event_name,
                        'region': event.get('AwsRegion', 'unknown'),
                        'source': event.get('EventSource', 'unknown')
                    }
                    
                    # Categorize events
                    if 'RunInstances' in event_name or 'TerminateInstances' in event_name:
                        resource_events['ec2_instances'].append(event_data)
                    elif 'Vpc' in event_name:
                        resource_events['vpcs'].append(event_data)
                    elif 'Subnet' in event_name:
                        resource_events['subnets'].append(event_data)
                    elif 'LoadBalancer' in event_name:
                        resource_events['load_balancers'].append(event_data)
                        
            except Exception as e:
                logger.warning(f"Error fetching events for {event_name}: {e}")
                
        logger.info(f"Found {sum(len(events) for events in resource_events.values())} resource events")
        return resource_events
    
    def create_growth_dataset(self, resource_events: Dict[str, List[Dict]], days_back: int = 90) -> pd.DataFrame:
        """
        Create a time series dataset from CloudTrail events.
        
        Args:
            resource_events: Events from CloudTrail
            days_back: Number of days to analyze
            
        Returns:
            DataFrame with daily resource counts
        """
        logger.info("Creating growth dataset from CloudTrail events...")
        
        # Create date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Initialize DataFrame
        df = pd.DataFrame(index=date_range)
        df.index.name = 'date'
        
        # Process each resource type
        for resource_type, events in resource_events.items():
            daily_counts = []
            running_count = 0
            
            for date in date_range:
                # Count events for this date
                date_events = [e for e in events if e['timestamp'].date() == date.date()]
                
                for event in date_events:
                    if 'Run' in event['event_name'] or 'Create' in event['event_name']:
                        running_count += 1
                    elif 'Terminate' in event['event_name'] or 'Delete' in event['event_name']:
                        running_count = max(0, running_count - 1)
                
                daily_counts.append(running_count)
            
            df[f'{resource_type}_count'] = daily_counts
        
        # Add total native objects
        df['total_native_objects'] = (
            df['ec2_instances_count'] + 
            df['vpcs_count'] + 
            df['subnets_count'] + 
            df['load_balancers_count']
        )
        
        # Add Management Token calculation
        df['management_tokens'] = (
            df['ec2_instances_count'] * 1 +  # 1 token per instance
            df['vpcs_count'] * 1 +           # 1 token per VPC
            df['subnets_count'] * 1 +        # 1 token per subnet
            df['load_balancers_count'] * 1   # 1 token per load balancer
        )
        
        logger.info(f"Created growth dataset with {len(df)} days of data")
        return df
    
    def analyze_growth_trends(self, df: pd.DataFrame) -> Dict:
        """
        Analyze growth trends using linear and polynomial regression.
        
        Args:
            df: Growth dataset DataFrame
            
        Returns:
            Dictionary with analysis results
        """
        logger.info("Analyzing growth trends...")
        
        # Prepare data
        X = np.arange(len(df)).reshape(-1, 1)
        y_tokens = df['management_tokens'].values
        y_objects = df['total_native_objects'].values
        
        # Linear regression for Management Tokens
        linear_model_tokens = LinearRegression()
        linear_model_tokens.fit(X, y_tokens)
        
        # Polynomial regression for Management Tokens
        poly_model_tokens = Pipeline([
            ('poly', PolynomialFeatures(degree=2)),
            ('linear', LinearRegression())
        ])
        poly_model_tokens.fit(X, y_tokens)
        
        # Linear regression for Native Objects
        linear_model_objects = LinearRegression()
        linear_model_objects.fit(X, y_objects)
        
        # Polynomial regression for Native Objects
        poly_model_objects = Pipeline([
            ('poly', PolynomialFeatures(degree=2)),
            ('linear', LinearRegression())
        ])
        poly_model_objects.fit(X, y_objects)
        
        # Calculate R-squared scores
        linear_score_tokens = linear_model_tokens.score(X, y_tokens)
        poly_score_tokens = poly_model_tokens.score(X, y_tokens)
        linear_score_objects = linear_model_objects.score(X, y_objects)
        poly_score_objects = poly_model_objects.score(X, y_objects)
        
        # Choose best model for each metric
        best_model_tokens = poly_model_tokens if poly_score_tokens > linear_score_tokens else linear_model_tokens
        best_model_objects = poly_model_objects if poly_score_objects > linear_score_objects else linear_model_objects
        
        analysis = {
            'current_tokens': int(df['management_tokens'].iloc[-1]),
            'current_objects': int(df['total_native_objects'].iloc[-1]),
            'linear_r2_tokens': linear_score_tokens,
            'poly_r2_tokens': poly_score_tokens,
            'linear_r2_objects': linear_score_objects,
            'poly_r2_objects': poly_score_objects,
            'best_model_tokens': 'polynomial' if poly_score_tokens > linear_score_tokens else 'linear',
            'best_model_objects': 'polynomial' if poly_score_objects > linear_score_objects else 'linear',
            'models': {
                'tokens': best_model_tokens,
                'objects': best_model_objects
            }
        }
        
        logger.info(f"Analysis complete. Current tokens: {analysis['current_tokens']}, Current objects: {analysis['current_objects']}")
        return analysis
    
    def predict_future_growth(self, analysis: Dict, months_ahead: int = 36) -> pd.DataFrame:
        """
        Predict future growth based on historical trends.
        
        Args:
            analysis: Analysis results from analyze_growth_trends
            months_ahead: Number of months to predict
            
        Returns:
            DataFrame with predictions
        """
        logger.info(f"Predicting growth for next {months_ahead} months...")
        
        # Create future dates
        last_date = datetime.now()
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=months_ahead * 30,  # Approximate days
            freq='D'
        )
        
        # Prepare prediction data
        X_future = np.arange(len(future_dates)).reshape(-1, 1)
        
        # Make predictions
        token_predictions = analysis['models']['tokens'].predict(X_future)
        object_predictions = analysis['models']['objects'].predict(X_future)
        
        # Create prediction DataFrame
        predictions_df = pd.DataFrame({
            'date': future_dates,
            'predicted_tokens': np.maximum(0, token_predictions).astype(int),
            'predicted_objects': np.maximum(0, object_predictions).astype(int)
        })
        
        # Add monthly summaries
        monthly_predictions = predictions_df.set_index('date').resample('M').mean()
        monthly_predictions = monthly_predictions.reset_index()
        monthly_predictions['month'] = monthly_predictions['date'].dt.strftime('%Y-%m')
        
        logger.info(f"Generated predictions for {len(predictions_df)} days")
        return monthly_predictions
    
    def generate_growth_report(self, analysis: Dict, predictions: pd.DataFrame, output_format: str = 'json') -> Dict:
        """
        Generate a comprehensive growth report.
        
        Args:
            analysis: Analysis results
            predictions: Future predictions
            output_format: Output format (json, csv, txt)
            
        Returns:
            Report data
        """
        logger.info("Generating growth report...")
        
        # Calculate key metrics
        current_tokens = analysis['current_tokens']
        current_objects = analysis['current_objects']
        
        # Predictions for key timepoints
        year_1_tokens = predictions.iloc[11]['predicted_tokens'] if len(predictions) > 11 else current_tokens
        year_2_tokens = predictions.iloc[23]['predicted_tokens'] if len(predictions) > 23 else current_tokens
        year_3_tokens = predictions.iloc[35]['predicted_tokens'] if len(predictions) > 35 else current_tokens
        
        year_1_objects = predictions.iloc[11]['predicted_objects'] if len(predictions) > 11 else current_objects
        year_2_objects = predictions.iloc[23]['predicted_objects'] if len(predictions) > 23 else current_objects
        year_3_objects = predictions.iloc[35]['predicted_objects'] if len(predictions) > 35 else current_objects
        
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'current_state': {
                'management_tokens': current_tokens,
                'native_objects': current_objects
            },
            'growth_analysis': {
                'model_accuracy_tokens': max(analysis['linear_r2_tokens'], analysis['poly_r2_tokens']),
                'model_accuracy_objects': max(analysis['linear_r2_objects'], analysis['poly_r2_objects']),
                'best_model_tokens': analysis['best_model_tokens'],
                'best_model_objects': analysis['best_model_objects']
            },
            'predictions': {
                'year_1': {
                    'management_tokens': int(year_1_tokens),
                    'native_objects': int(year_1_objects),
                    'token_growth': int(year_1_tokens - current_tokens),
                    'object_growth': int(year_1_objects - current_objects)
                },
                'year_2': {
                    'management_tokens': int(year_2_tokens),
                    'native_objects': int(year_2_objects),
                    'token_growth': int(year_2_tokens - current_tokens),
                    'object_growth': int(year_2_objects - current_objects)
                },
                'year_3': {
                    'management_tokens': int(year_3_tokens),
                    'native_objects': int(year_3_objects),
                    'token_growth': int(year_3_tokens - current_tokens),
                    'object_growth': int(year_3_objects - current_objects)
                }
            },
            'recommendations': {
                'immediate': f"Current Management Token requirement: {current_tokens}",
                'year_1': f"Plan for {int(year_1_tokens)} Management Tokens",
                'year_2': f"Plan for {int(year_2_tokens)} Management Tokens", 
                'year_3': f"Plan for {int(year_3_tokens)} Management Tokens"
            }
        }
        
        logger.info("Growth report generated successfully")
        return report
    
    def create_growth_visualization(self, historical_df: pd.DataFrame, predictions_df: pd.DataFrame, 
                                  output_path: str) -> None:
        """
        Create a visualization of historical data and predictions.
        
        Args:
            historical_df: Historical data
            predictions_df: Future predictions
            output_path: Path to save the visualization
        """
        logger.info(f"Creating growth visualization: {output_path}")
        
        # Set up the plot
        plt.figure(figsize=(15, 10))
        
        # Historical data
        plt.subplot(2, 1, 1)
        plt.plot(historical_df.index, historical_df['management_tokens'], 
                label='Historical Management Tokens', color='blue', linewidth=2)
        plt.title('Historical Management Token Usage', fontsize=14, fontweight='bold')
        plt.ylabel('Management Tokens')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Predictions
        plt.subplot(2, 1, 2)
        plt.plot(predictions_df['date'], predictions_df['predicted_tokens'], 
                label='Predicted Management Tokens', color='red', linewidth=2, linestyle='--')
        plt.title('3-Year Management Token Prediction', fontsize=14, fontweight='bold')
        plt.ylabel('Management Tokens')
        plt.xlabel('Date')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualization saved to {output_path}")
    
    def run_complete_analysis(self, days_back: int = 90, months_ahead: int = 36, 
                            output_format: str = 'json') -> Tuple[Dict, pd.DataFrame, pd.DataFrame]:
        """
        Run complete historical analysis using CloudTrail data.
        
        Args:
            days_back: Days of historical data to analyze
            months_ahead: Months to predict into the future
            output_format: Output format for reports
            
        Returns:
            Tuple of (analysis_results, predictions, historical_data)
        """
        logger.info("Starting complete CloudTrail-based historical analysis...")
        
        # Get CloudTrail events
        resource_events = self.get_resource_events(days_back)
        
        # Create growth dataset
        historical_df = self.create_growth_dataset(resource_events, days_back)
        
        # Analyze trends
        analysis = self.analyze_growth_trends(historical_df)
        
        # Predict future growth
        predictions = self.predict_future_growth(analysis, months_ahead)
        
        # Generate report
        report = self.generate_growth_report(analysis, predictions, output_format)
        
        logger.info("Complete CloudTrail analysis finished")
        return report, predictions, historical_df 