# Google Cloud Run Deployment Guide (Using Cloud Console UI)

## Prerequisites

1. Google Cloud account with billing enabled
2. A Google Cloud project created
3. Docker installed (for local testing only)

## Deployment Steps

### Overview

This guide uses a dedicated service account for the Streamlit dashboard, which provides:
- **Better security** through principle of least privilege
- **Easier permission management** - grant only necessary BigQuery and Secret Manager access
- **Audit trail** - track which resources the dashboard accesses
- **Isolation** - separate from other services in your project

### Step 1: Enable Required APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project from the dropdown at the top
3. Navigate to **APIs & Services** > **Library**
4. Search for and enable:
   - **Cloud Run API**
   - **Cloud Build API**
   - **Secret Manager API** (for credentials)

### Step 2: Create a Dedicated Service Account

Creating a dedicated service account provides better security and access control.

1. Navigate to **IAM & Admin** > **Service Accounts** in the left menu
2. Click **CREATE SERVICE ACCOUNT**
3. Configure the service account:
   - **Service account name**: `streamlit-dashboard-sa`
   - **Service account ID**: `streamlit-dashboard-sa` (auto-populated)
   - **Description**: `Service account for Streamlit dashboard Cloud Run service`
   - Click **CREATE AND CONTINUE**
4. Grant roles (add each of these):
   - Click **ADD ANOTHER ROLE** and select:
     - **BigQuery Data Viewer** (to read from BigQuery)
     - **BigQuery Job User** (to run queries)
     - **Secret Manager Secret Accessor** (to access credentials)
   - Click **CONTINUE**
5. Skip "Grant users access to this service account" (optional)
6. Click **DONE**
7. Note the service account email: `streamlit-dashboard-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com`

### Step 3: Store BigQuery Credentials in Secret Manager

1. Navigate to **Security** > **Secret Manager** in the left menu
2. Click **CREATE SECRET**
3. Configure the secret:
   - **Name**: `bigquery-credentials`
   - **Secret value**: Paste the contents of your BigQuery credentials JSON file
   - Click **CREATE SECRET**
4. After creation, click on the secret name
5. Go to **PERMISSIONS** tab
6. Click **GRANT ACCESS**
7. Add principal: `streamlit-dashboard-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com`
   - (Use the service account email from Step 2)
8. Assign role: **Secret Manager Secret Accessor**
9. Click **SAVE**

**Alternative Approach (No Secrets Needed):**
If your BigQuery data is in the same project and you don't need external credentials, you can skip this step. The service account created in Step 2 already has BigQuery access. Just don't mount any secrets in Step 5, and your app will use the service account's identity directly.

### What You Actually Need

**Minimum Required Configuration:**
- ✅ **Service account** with BigQuery Data Viewer and BigQuery Job User roles (Step 2)
- ✅ **Environment variable**: `GOOGLE_CLOUD_PROJECT_ID` 
- ✅ That's it! No secrets needed if your data is in the same project

**Only add secrets if:**
- ❌ You need to access BigQuery in a **different** Google Cloud project
- ❌ You need to use a **specific service account key file** for compliance/auditing
- ❌ Your organization requires explicit credential files

**How it works:**
When Cloud Run starts your container, the service account identity is automatically available. The BigQuery client library reads this identity and authenticates automatically - no credential files needed!

### Step 4: Prepare Your Code

1. Ensure all files are ready:
   - `app.py`
   - `utilities.py`
   - `requirements.txt`
   - `Dockerfile`

2. Create a ZIP file or push to a Git repository (GitHub, GitLab, Bitbucket, or Cloud Source Repository)

### Step 5: Deploy to Cloud Run

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
8. Expand **CONTAINER, VARIABLES & SECRETS, CONNECTIONS, SECURITY**
9. Go to **SECURITY** tab:
   - **Service account**: Select `streamlit-dashboard-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com`
10. Go to **VARIABLES & SECRETS** tab:
    - Click **ADD VARIABLE**
      - **Name**: `GOOGLE_CLOUD_PROJECT_ID`
      - **Value**: `etl-testing-478716` (or your project ID)
    - **Optional - Only if using external credentials**: Click **ADD SECRET**
      - **Name**: `BIGQUERY_CREDENTIALS_PATH`
      - **Select secret**: `bigquery-credentials`
      - **Reference method**: Mounted as volume
      - **Mount path**: `/secrets/bigquery-credentials`
      - **Note**: Skip this if your BigQuery data is in the same project - the service account will authenticate automatically
11. Go to **CONTAINER** tab (optional optimizations):
    - **Memory**: `1 GiB`
    - **CPU**: `1`
    - **Request timeout**: `300` seconds
    - **Maximum requests per container**: `80`
    - **Minimum instances**: `0` (scale to zero)
    - **Maximum instances**: `10`
12. Click **CREATE**

### Step 6: Verify Your utilities.py

Your `utilities.py` is already configured to handle both authentication methods automatically:

```python
def init_bigquery_client() -> bigquery.Client:
    """Initialize BigQuery client"""
    # First try mounted secret (Cloud Run with Secret Manager)
    bq_credentials_path = '/secrets/bigquery-credentials'
    
    # Fall back to environment variable (local development)
    if not os.path.exists(bq_credentials_path):
        bq_credentials_path = os.getenv('BIGQUERY_CREDENTIALS_PATH')
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")
    
    # If credentials file exists, use it
    if bq_credentials_path and os.path.exists(bq_credentials_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = bq_credentials_path
        print(f"Using BigQuery credentials: {bq_credentials_path}")
    else:
        # Use default credentials (Cloud Run service account identity)
        print("Using default credentials (service account)")
    
    return bigquery.Client(project=project_id)
```

**How it works:**
1. Checks for mounted secret (if you configured one)
2. Falls back to `.env` file (for local development)
3. **Uses service account identity** if no credentials file exists (production default)

✅ **No changes needed** - the code already works with your service account!

### Step 7: Access Your Application

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

### Understanding Authentication Options

**Allow Unauthenticated (Public Access):**
- ✅ Anyone with the URL can access the dashboard
- ✅ Simple to use - just share the link
- ✅ No login required
- ⚠️ Publicly accessible on the internet
- ⚠️ Consider if your data should be public

**Require Authentication (Private Access):**
- ✅ Only authorized users can access
- ✅ Better security for sensitive data
- ✅ Audit trail of who accessed
- ⚠️ Users need Google Cloud credentials
- ⚠️ More complex access process

### How Authentication Affects Usage

#### With Authentication Required:

**For End Users:**
1. **Cannot access via browser directly** - clicking the URL shows "403 Forbidden"
2. **Must be granted Cloud Run Invoker role** by a project admin
3. **Need one of these access methods:**
   - **Option A: Using gcloud CLI** (technical users only)
     ```bash
     gcloud auth login
     curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
       https://streamlit-dashboard-xxxxx.run.app
     ```
     *Not practical for a web dashboard*
   
   - **Option B: Identity-Aware Proxy (IAP)** (recommended for dashboards)
     - Provides a login page in the browser
     - Users sign in with Google accounts
     - Works like normal web browsing after login
     - **Best for Streamlit dashboards with multiple users**
   
   - **Option C: Proxy/Gateway** 
     - Build a custom auth proxy
     - Requires additional infrastructure

**Recommendation for Your Use Case:**
- **Internal team dashboard with sensitive BigQuery data?** → Use authentication with IAP
- **Public analytics dashboard?** → Allow unauthenticated access
- **Mixed audience?** → Consider creating a filtered view of data for public access

### Make Service Private

1. Go to **Cloud Run** > your service
2. Click **EDIT & DEPLOY NEW REVISION**
3. In the **Authentication** section, select **Require authentication**
4. Click **DEPLOY**
5. Go to **PERMISSIONS** tab
6. Click **GRANT ACCESS**
7. Add principals (users who need access):
   - **For individual users**: `user:someone@example.com`
   - **For your whole domain**: `domain:yourcompany.com`
   - **For a group**: `group:team@yourcompany.com`
8. Assign role: **Cloud Run Invoker**
9. Click **SAVE**

### Set Up Identity-Aware Proxy (IAP) for Browser Access

IAP provides a user-friendly login page for authenticated services. Here's how to set it up:

#### Step 1: Enable IAP
1. Go to **Security** > **Identity-Aware Proxy**
2. Click **ENABLE API** if prompted
3. Configure OAuth consent screen:
   - Go to **OAuth consent screen** tab
   - Select **Internal** (for workspace users) or **External** (for any Google account)
   - Fill in application name: "Streamlit Dashboard"
   - Add your email
   - Click **SAVE**

#### Step 2: Configure IAP for Cloud Run
1. In IAP page, find **Cloud Run** section
2. Toggle on IAP for your `streamlit-dashboard` service
3. Add members who should have access:
   - Click **ADD PRINCIPAL**
   - Enter email addresses
   - Select role: **IAP-secured Web App User**
   - Click **SAVE**

#### Step 3: Access the Dashboard
1. Users navigate to the Cloud Run URL
2. They're prompted to sign in with Google
3. After authentication, they access the dashboard normally
4. Session persists - no need to re-authenticate frequently

**Note:** IAP works best when your Cloud Run service requires authentication AND uses the IAP headers for authorization.

### Hybrid Approach: Public Dashboard with Admin Features

If you want some features public and others private, consider:

1. **Keep Cloud Run unauthenticated** (public access)
2. **Add authentication in Streamlit app code** using:
   - Streamlit's built-in authentication
   - OAuth with Google Sign-In
   - Simple password protection

Example with simple authentication in your Streamlit app:

```python
import streamlit as st

def check_password():
    """Returns True if user has entered correct password"""
    def password_entered():
        if st.session_state["password"] == st.secrets["passwords"]["admin"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", 
                     on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password",
                     on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# In your app.py, at the top of main content:
if not check_password():
    st.stop()
```

Then create `.streamlit/secrets.toml`:
```toml
[passwords]
admin = "your-secret-password-here"
```

### Access Patterns Comparison

| Access Method | User Experience | Security | Setup Complexity | Best For |
|---------------|----------------|----------|------------------|----------|
| **Unauthenticated** | ⭐⭐⭐⭐⭐ Just click link | ⭐ Public | ⭐ None | Public dashboards, demos |
| **Cloud Run Auth + CLI** | ⭐ Complex commands | ⭐⭐⭐⭐⭐ Very secure | ⭐⭐ Medium | API endpoints, services |
| **Cloud Run Auth + IAP** | ⭐⭐⭐⭐ Browser login | ⭐⭐⭐⭐⭐ Very secure | ⭐⭐⭐⭐ Complex | Internal dashboards |
| **App-level Auth** | ⭐⭐⭐ Password entry | ⭐⭐⭐ Moderate | ⭐⭐ Medium | Small teams, simple needs |

### Recommendation for Your Dashboard

**For your Streamlit PostHog Analytics dashboard:**

1. **Start with unauthenticated access** if:
   - Your team is small (~5-10 people) and you trust everyone with the link
   - The aggregated data doesn't contain PII or sensitive business secrets
   - You want maximum ease of access
   - You can obscure the URL (don't share publicly)

2. **Add Cloud Run authentication with IAP** if:
   - You have sensitive user data or business metrics
   - You need compliance (GDPR, HIPAA, SOC2)
   - You want to audit who accessed the dashboard
   - You have 10+ users who need different permission levels

3. **Use simple app-level password** if:
   - Quick protection for a small team
   - Temporary solution while setting up IAP
   - You don't need per-user tracking

**You can always change this setting later without redeploying your code!**

### How to Change Authentication Later

To switch from unauthenticated to authenticated:
1. Go to **Cloud Run** > your service
2. Click **EDIT & DEPLOY NEW REVISION**  
3. Change **Authentication** setting
4. Add users in **PERMISSIONS** tab
5. Click **DEPLOY**

No code changes needed - takes 1-2 minutes.



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

### Build Failures

If your Cloud Build fails, check these common issues:

1. **"No such file or directory" errors:**
   - Verify all files referenced in Dockerfile exist in your repository
   - Check that files are committed and pushed to your Git repository
   - Review the Dockerfile COPY commands

2. **"No logs found" message:**
   - Wait a few moments and refresh - logs may be delayed
   - Check **Cloud Build** > **History** for the build status
   - Verify you have the correct project selected
   - Check IAM permissions: you need `Logs Viewer` role

3. **Python package installation failures:**
   - Check `requirements.txt` for typos or version conflicts
   - Some packages may require additional system dependencies
   - Increase build timeout if packages are large

4. **Memory or timeout errors during build:**
   - Go to **Cloud Build** > **Settings**
   - Increase machine type or timeout
   - Or simplify your `requirements.txt`

**To view build details:**
1. Go to **Cloud Build** > **History**
2. Find your build (filter by date/time)
3. Click on the build ID
4. View the full build log and error messages

**Alternative ways to view logs:**
1. **In Cloud Run during deployment:**
   - Click **SHOW LOGS** at the bottom of the deployment screen
   - Logs stream in real-time during build

2. **In Cloud Logging:**
   - Go to **Logging** > **Logs Explorer**
   - Select resource type: **Cloud Build**
   - Select your build ID
   
3. **Check permissions if no logs appear:**
   - Go to **IAM & Admin** > **IAM**
   - Verify your account has role: **Logging/Logs Viewer** or **Project Viewer**
   - If missing, add the role to your account

4. **Via command line:**
   ```bash
   # List recent builds
   gcloud builds list --limit=5
   
   # View specific build logs (replace BUILD_ID)
   gcloud builds log BUILD_ID
   ```

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
2. Verify service account has proper permissions:
   - Go to **IAM & Admin** > **IAM**
   - Find `streamlit-dashboard-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com`
   - Ensure it has these roles:
     - BigQuery Data Viewer
     - BigQuery Job User
     - Secret Manager Secret Accessor
3. Verify the service account is set for Cloud Run:
   - Go to **Cloud Run** > your service > **SECURITY** tab
   - Confirm correct service account is selected
4. Check BigQuery API is enabled:
   - Go to **APIs & Services** > **Enabled APIs**
   - Verify "BigQuery API" is in the list

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
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)

## Quick Reference: Service Account Setup

For quick copy-paste when creating your service account:

**Service Account Details:**
- Name: `streamlit-dashboard-sa`
- Description: `Service account for Streamlit dashboard Cloud Run service`

**Required Roles:**
- BigQuery Data Viewer
- BigQuery Job User  
- Secret Manager Secret Accessor (if using secrets)

**Service Account Email Format:**
```
streamlit-dashboard-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com
```

Replace `YOUR-PROJECT-ID` with your actual Google Cloud project ID (e.g., `etl-testing-478716`).

---

## TL;DR: Simplified Deployment for Same-Project BigQuery

If your BigQuery data is in `etl-testing-478716` (same project as Cloud Run):

**You only need:**
1. ✅ Create service account with BigQuery roles (Step 2)
2. ✅ Set service account in Cloud Run (Step 5, section 9)
3. ✅ Add env var `GOOGLE_CLOUD_PROJECT_ID=etl-testing-478716` (Step 5, section 10)
4. ✅ Deploy!

**You DON'T need:**
- ❌ Step 3 (Secret Manager) - skip it entirely
- ❌ Mounting any secrets in Step 5
- ❌ Credential JSON files

The service account authenticates automatically using its identity. Simple and secure!
