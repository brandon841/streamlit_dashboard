import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound
except ImportError:
    print("ERROR: Google Cloud BigQuery not installed")
    print("Install with: pip install google-cloud-bigquery pyarrow")
    exit(1)

def init_bigquery_client() -> bigquery.Client:
    """Initialize BigQuery client"""
    # First try mounted secret (Cloud Run)
    bq_credentials_path = '/secrets/bigquery-credentials'
    
    # Fall back to environment variable
    if not os.path.exists(bq_credentials_path):
        bq_credentials_path = os.getenv('BIGQUERY_CREDENTIALS_PATH')
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")
    
    if bq_credentials_path and os.path.exists(bq_credentials_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = bq_credentials_path
        print(f"Using BigQuery credentials: {bq_credentials_path}")
    
    return bigquery.Client(project=project_id)