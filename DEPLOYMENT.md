# Google Cloud Run Deployment Guide (Using Cloud Console UI)

## Prerequisites

1. Google Cloud account with billing enabled
2. A Google Cloud project created
3. Docker installed (for local testing only)

## Deployment Steps

### Step 1: Enable Required APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project from the dropdown at the top
3. Navigate to **APIs & Services** > **Library**
4. Search for and enable:
   - **Cloud Run API**
   - **Cloud Build API**
   - **Secret Manager API** (for credentials)

### Step 2: Store BigQuery Credentials in Secret Manager

1. Navigate to **Security** > **Secret Manager** in the left menu
2. Click **CREATE SECRET**
3. Configure the secret:
   - **Name**: `bigquery-credentials`
   - **Secret value**: Paste the contents of your BigQuery credentials JSON file
   - Click **CREATE SECRET**
4. After creation, click on the secret name
5. Go to **PERMISSIONS** tab
6. Click **GRANT ACCESS**
7. Add principal: `YOUR-PROJECT-NUMBER-compute@developer.gserviceaccount.com`
   - To find your project number: Go to **Home** > **Dashboard**, it's shown under "Project info"
8. Assign role: **Secret Manager Secret Accessor**
9. Click **SAVE**

### Step 3: Prepare Your Code

1. Ensure all files are ready:
   - `app.py`
   - `utilities.py`
   - `requirements.txt`
   - `Dockerfile`
   - `df_explanation.md`

2. Create a ZIP file or push to a Git repository (GitHub, GitLab, Bitbucket, or Cloud Source Repository)

### Step 4: Deploy to Cloud Run

#### Option A: Deploy from GitHub Repository (Recommended)

1. Navigate to **Cloud Run** in the left menu
2. Click **CREATE SERVICE**
3. Select **Continuously deploy from a repository (source or function)**
4. Click **SET UP WITH CLOUD BUILD**
5. Configure repository:
   - Click **CONNECT REPOSITORY**
   - Select your repository provider (GitHub, Bitbucket, etc.)
   - Authenticate and select your repository
   - Choose branch (e.g., `main`)
   - Click **NEXT**
6. Configure build:
   - **Build type**: Dockerfile
   - **Source location**: `/Dockerfile`
   - Click **SAVE**
7. Configure service settings:
   - **Service name**: `streamlit-dashboard`
   - **Region**: `us-central1` (or your preferred region)
   - **Authentication**: Select **Allow unauthenticated invocations** (or require authentication if needed)
8. Click **CONTAINER, VARIABLES & SECRETS, CONNECTIONS, SECURITY**
9. Go to **VARIABLES & SECRETS** tab:
   - Click **ADD VARIABLE**
     - **Name**: `GOOGLE_CLOUD_PROJECT_ID`
     - **Value**: `etl-testing-478716` (or your project ID)
   - Click **ADD SECRET**
     - **Name**: `BIGQUERY_CREDENTIALS_PATH`
     - **Select secret**: `bigquery-credentials`
     - **Reference method**: Mounted as volume
     - **Mount path**: `/secrets/bigquery-credentials`
10. Go to **CONTAINER** tab (optional optimizations):
    - **Memory**: `1 GiB`
    - **CPU**: `1`
    - **Request timeout**: `300` seconds
    - **Maximum requests per container**: `80`
    - **Minimum instances**: `0` (scale to zero)
    - **Maximum instances**: `10`
11. Click **CREATE**

#### Option B: Deploy from Local Source (Using Cloud Shell)

1. Navigate to **Cloud Run** in the left menu
2. Click **CREATE SERVICE**
3. Select **Deploy one revision from an existing container image**
4. Click **TEST WITH CLOUD SHELL**
5. In Cloud Shell, run:
   ```bash
   # Upload your files (use the upload button in Cloud Shell)
   # Or clone from your repository
   git clone https://github.com/brandon841/streamlit_dashboard.git
   cd streamlit_dashboard
   
   # Deploy
   gcloud run deploy streamlit-dashboard \
     --source . \
     --region us-central1 \
     --allow-unauthenticated
   ```
6. Follow prompts to configure environment variables

#### Option C: Build and Deploy Manually

1. Open **Cloud Shell** (icon at top right of console)
2. Upload your project files or clone from Git
3. Build the container:
   ```bash
   PROJECT_ID=$(gcloud config get-value project)
   docker build -t gcr.io/$PROJECT_ID/streamlit-dashboard:latest .
   docker push gcr.io/$PROJECT_ID/streamlit-dashboard:latest
   ```
4. Go to **Cloud Run** > **CREATE SERVICE**
5. Select **Deploy one revision from an existing container image**
6. Click **SELECT**
7. Choose **Artifact Registry** or **Container Registry**
8. Select your image: `gcr.io/YOUR-PROJECT/streamlit-dashboard:latest`
9. Configure service (same as Option A, steps 7-11)
10. Click **CREATE**

### Step 5: Update Environment Variables in utilities.py

If using mounted secret, update your `utilities.py` to read from the mounted path:

```python
def init_bigquery_client() -> bigquery.Client:
    """Initialize BigQuery client"""
    # First try mounted secret (Cloud Run)
    bq_credentials_path = '/secrets/bigquery-credentials'
    if not os.path.exists(bq_credentials_path):
        # Fall back to env variable
        bq_credentials_path = os.getenv('BIGQUERY_CREDENTIALS_PATH')
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")
    
    if bq_credentials_path and os.path.exists(bq_credentials_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = bq_credentials_path
    
    return bigquery.Client(project=project_id)
```

### Step 6: Access Your Application

1. After deployment completes, you'll see a **Service URL** (e.g., `https://streamlit-dashboard-xxxxx-uc.a.run.app`)
2. Click the URL to open your application
3. Bookmark the URL for easy access

## Managing Your Deployment

### View Service Details

1. Navigate to **Cloud Run**
2. Click on your service name
3. View metrics, logs, and configuration

### View Logs

1. In your Cloud Run service page
2. Click the **LOGS** tab
3. View real-time logs and errors
4. Use filters to search specific log entries

### Update Deployment

#### If using continuous deployment (Option A):
- Simply push changes to your Git repository
- Cloud Build will automatically rebuild and deploy

#### For manual updates:
1. Go to **Cloud Run** > your service
2. Click **EDIT & DEPLOY NEW REVISION**
3. Update settings or environment variables
4. Click **DEPLOY**

### Modify Environment Variables

1. Go to **Cloud Run** > your service
2. Click **EDIT & DEPLOY NEW REVISION**
3. Go to **VARIABLES & SECRETS** tab
4. Add, edit, or remove variables
5. Click **DEPLOY**

### Adjust Resources

1. Go to **Cloud Run** > your service
2. Click **EDIT & DEPLOY NEW REVISION**
3. Go to **CONTAINER** tab
4. Adjust:
   - Memory allocation (128 MiB - 32 GiB)
   - CPU allocation (1-8 CPUs)
   - Request timeout (1-3600 seconds)
   - Max concurrent requests (1-1000)
   - Min/max instances
5. Click **DEPLOY**

## Authentication Setup

### Make Service Private

1. Go to **Cloud Run** > your service
2. Click **PERMISSIONS** tab
3. Click **ADD PRINCIPAL**
4. Enter user email: `user@example.com`
5. Select role: **Cloud Run Invoker**
6. Click **SAVE**
7. Go back to **DETAILS** tab
8. Under **Security**, change to **Require authentication**

### Access Private Service

Users will need to:
1. Install gcloud CLI
2. Run: `gcloud auth login`
3. Access via: `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" SERVICE_URL`

Or use Identity-Aware Proxy (IAP) for browser access.

## Local Testing with Docker

Before deploying, test locally:

```bash
# Build the image
docker build -t streamlit-dashboard .

# Run locally
docker run -p 8080:8080 \
  -e GOOGLE_CLOUD_PROJECT_ID=etl-testing-478716 \
  -v $(pwd)/credentials.json:/secrets/bigquery-credentials \
  streamlit-dashboard

# Access at http://localhost:8080
```

## Monitoring and Alerts

### Set Up Monitoring

1. Go to **Cloud Run** > your service
2. Click **METRICS** tab
3. View:
   - Request count
   - Request latency
   - CPU utilization
   - Memory utilization
   - Instance count

### Create Alerts

1. Go to **Monitoring** > **Alerting**
2. Click **CREATE POLICY**
3. Select metric (e.g., "Cloud Run > Request count")
4. Configure conditions
5. Set notification channels
6. Click **SAVE**

## Pricing Estimate

Cloud Run charges based on:
- **CPU and memory** usage during request processing
- **Number of requests**
- **Networking** (egress)

### Free Tier (per month):
- 2 million requests
- 360,000 GB-seconds of memory
- 180,000 vCPU-seconds
- 1 GB network egress to North America

### Estimated Cost for Low Traffic:
- Most small applications stay within free tier
- After free tier: ~$0.10-$1.00 per day for modest traffic

View detailed pricing: [Cloud Run Pricing](https://cloud.google.com/run/pricing)

## Troubleshooting

### Service Won't Start

1. Check **LOGS** tab for error messages
2. Common issues:
   - Port binding: Ensure Streamlit uses `$PORT` environment variable
   - Missing dependencies: Check `requirements.txt`
   - Memory errors: Increase memory allocation

### BigQuery Authentication Errors

1. Verify secret is mounted correctly:
   - Go to service > **EDIT & DEPLOY NEW REVISION**
   - Check **VARIABLES & SECRETS** tab
   - Ensure secret path is `/secrets/bigquery-credentials`
2. Verify service account has Secret Manager access
3. Check BigQuery API is enabled

### Timeout Errors

1. Go to service > **EDIT & DEPLOY NEW REVISION**
2. Go to **CONTAINER** tab
3. Increase **Request timeout** to 300-600 seconds
4. Click **DEPLOY**

### High Costs

1. Check **METRICS** tab for unusual traffic patterns
2. Set maximum instances to control scaling
3. Enable **Minimum instances** = 0 for scale-to-zero
4. Review and optimize BigQuery queries

## Clean Up

### Delete Service

1. Go to **Cloud Run**
2. Select your service checkbox
3. Click **DELETE** at the top
4. Confirm deletion

### Delete Container Images

1. Go to **Artifact Registry** or **Container Registry**
2. Find your image
3. Select and click **DELETE**

### Delete Secrets

1. Go to **Secret Manager**
2. Select your secret
3. Click **DELETE**

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Streamlit with Cloud Run](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Cloud Run Pricing Calculator](https://cloud.google.com/products/calculator)
