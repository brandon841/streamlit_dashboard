# PostHog Analytics Dashboard

Interactive Streamlit dashboard for exploring aggregated user and session data from BigQuery.

Can view live dashboard hosted by Google Run at - https://streamlit-dashboard-25415421028.us-central1.run.app/

## Features

- **User Analytics**: View and filter user-level aggregated metrics
- **Session Analytics**: Explore session-level data with event filtering
- **Quick Insights**: Visualize key metrics and trends
- **Interactive Filtering**: Search, filter, and customize data views
- **Data Export**: Download filtered data as CSV

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
Create a `.env` file with:
```
GOOGLE_CLOUD_PROJECT_ID=your-project-id
BIGQUERY_CREDENTIALS_PATH=/path/to/your/credentials.json
```

3. Run the application:
```bash
streamlit run app.py
```

4. Open your browser to `http://localhost:8501`

## Usage

- Navigate between tabs to explore different data views
- Use filters and search to narrow down results
- Select columns to customize displayed data
- Download filtered data for further analysis
- Data is cached for 1 hour; use the "Clear cache" option to force refresh

## Data Sources

- **People Aggregated**: User-level metrics from PostHog
- **Sessions Aggregated**: Session-level data with events and interactions

## Deployment to Google Cloud Run

Deploy the app to Google Cloud Run for production use:

```bash
# Quick deployment (builds and deploys in one step)
gcloud run deploy streamlit-dashboard \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT_ID=your-project-id
```

For detailed deployment instructions, authentication setup, and troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Local Docker Testing

```bash
# Build and run with Docker
docker build -t streamlit-dashboard .
docker run -p 8080:8080 streamlit-dashboard
```

Access at `http://localhost:8080`
