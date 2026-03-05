import streamlit as st
from utilities import init_bigquery_client
from google.cloud import bigquery
from google.cloud import storage
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone

# Page configuration
st.set_page_config(
    page_title="PostHog Analytics Dashboard",
    page_icon="",
    layout="wide"
)

st.title("PostHog Analytics Dashboard")
st.markdown("Interactive exploration of aggregated user and session data")

# Configuration
CACHE_BUCKET_NAME = "heyyall-dashboard-cache"  # Change this to your bucket name
CACHE_REFRESH_HOURS = 24  # Refresh cache daily

# Cache the data loading to avoid repeated queries
@st.cache_data(ttl=3600)  # Cache for 1 hour in Streamlit memory
def load_data():
    """Load data from Cloud Storage cache or BigQuery if cache is stale"""
    bq = init_bigquery_client()
    storage_client = storage.Client()
    bucket = storage_client.bucket(CACHE_BUCKET_NAME)
    
    tables = {
        'people': 'etl-testing-478716.posthog_aggregated_prod.people_aggregated',
        'sessions': 'etl-testing-478716.posthog_aggregated_prod.sessions_aggregated',
        'churn': 'etl-testing-478716.posthog_aggregated_prod.user_churn_state',
        'users': 'etl-testing-478716.firebase_etl_prod.users'
    }
    
    dataframes = {}
    load_info = []  # Track where data came from
    
    for table_name, table_path in tables.items():
        blob_name = f"cache/{table_name}.parquet"
        blob = bucket.blob(blob_name)
        
        should_query_bq = True
        
        # Check if cache exists and is recent
        if blob.exists():
            blob.reload()
            cache_age = datetime.now(timezone.utc) - blob.updated
            
            if cache_age < timedelta(hours=CACHE_REFRESH_HOURS):
                # Load from cache (nearly free!)
                try:
                    # Download to memory and read as parquet
                    cache_data = blob.download_as_bytes()
                    dataframes[table_name] = pd.read_parquet(pd.io.common.BytesIO(cache_data))
                    should_query_bq = False
                    hours_old = cache_age.seconds // 3600
                    load_info.append(f"{table_name}: cache ({hours_old}h old)")
                except Exception as e:
                    # If cache read fails, fall back to BigQuery
                    load_info.append(f"{table_name}: cache failed, using BigQuery")
        
        # Query BigQuery if cache doesn't exist or is stale
        if should_query_bq:
            # Optimize users query to only select needed columns
            if table_name == 'users':
                query = f"SELECT user_id, fullName, email FROM `{table_path}`"
            else:
                query = f"SELECT * FROM `{table_path}`"
            
            dataframes[table_name] = bq.query(query).to_dataframe()
            load_info.append(f"{table_name}: BigQuery (cached for 24h)")
            
            # Save to cache for next time
            try:
                parquet_buffer = pd.io.common.BytesIO()
                dataframes[table_name].to_parquet(parquet_buffer, index=False)
                parquet_buffer.seek(0)
                blob.upload_from_file(parquet_buffer, content_type='application/octet-stream')
            except Exception as e:
                # Silently fail cache write - data is still available
                pass
    
    status_message = " | ".join(load_info)
    return dataframes['people'], dataframes['sessions'], dataframes['churn'], dataframes['users'], status_message

# Load data
try:
    with st.spinner("Loading data..."):
        people_df, sessions_df, churn_df, user_df, load_status = load_data()
    
    # Show load status as toast notification
    st.toast(f"✓ Data loaded: {load_status}", icon="✅")
    
    #merging user_df to churn_df on user_id
    churn_df = churn_df.merge(user_df[['user_id', 'fullName', 'email']], on='user_id', how='left')
    
    #dropping sessions with null start_timestamp as they are likely incomplete/invalid
    sessions_df = sessions_df.dropna(subset=['start_timestamp'])

    #getting list of sessions with duration = 0 and autocapture_count = 0 ==> likely abnormal sessions that are artifacts from posthog
    bad_session_df = sessions_df[(sessions_df['autocapture_count'] == 0) & (sessions_df['session_duration'] == 0)].session_id.copy()
    sessions_df = sessions_df[~sessions_df['session_id'].isin(bad_session_df)]
    
    st.success(f"Data loaded successfully! {len(people_df)} users, {len(sessions_df)} sessions, {len(churn_df)} churn records")
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

# Create tabs for different views
tab1, tab2, tab3 = st.tabs(["People Data", "Sessions Data", "Churn Data"])

# TAB 1: PEOPLE DATA
with tab1:
    st.header("User Analytics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Users", f"{len(people_df):,}")
    with col2:
        avg_sessions = people_df['total_sessions'].mean()
        st.metric("Avg Sessions/User", f"{avg_sessions:.1f}")
    with col3:
        total_sessions = people_df['total_sessions'].sum()
        st.metric("Total Sessions", f"{total_sessions:,}")
    with col4:
        business_users = people_df['businessUser'].sum()
        st.metric("Business Users", f"{business_users:,}")
    
    st.subheader("Filter & Search")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        # Business user filter
        user_type = st.selectbox(
            "User Type",
            ["All Users", "Business Users", "Non-Business Users"]
        )
        
        # Session count filter
        min_sessions = st.slider(
            "Minimum Sessions",
            min_value=0,
            max_value=int(people_df['total_sessions'].max()),
            value=0
        )

    with col2:
        # Country filter
        countries = ["All"] + sorted(people_df['country'].dropna().unique().tolist())
        selected_country = st.selectbox("Country", countries)
        
        # Search by name/username/email
        search_term = st.text_input("Search (name, username, or email)")
    
    # Apply filters
    filtered_people = people_df.copy()
    
    if user_type == "Business Users":
        filtered_people = filtered_people[filtered_people['businessUser'] == True]
    elif user_type == "Non-Business Users":
        filtered_people = filtered_people[filtered_people['businessUser'] == False]
    
    filtered_people = filtered_people[filtered_people['total_sessions'] >= min_sessions]
    
    if selected_country != "All":
        filtered_people = filtered_people[filtered_people['country'] == selected_country]
    
    if search_term:
        mask = (
            filtered_people['fullName'].str.contains(search_term, case=False, na=False) |
            filtered_people['username'].str.contains(search_term, case=False, na=False) |
            filtered_people['email'].str.contains(search_term, case=False, na=False)
        )
        filtered_people = filtered_people[mask]
    
    st.info(f"Showing {len(filtered_people)} of {len(people_df)} users")
    
    # Column selection
    st.subheader("Select Columns to Display")
    with st.expander("Column Info"):
        st.markdown("""
                        **Columns:**
            - `user_id` - Firebase user ID (required)
            - `total_sessions` - Total number of sessions for user
            - `avg_session_duration` - Average session length in seconds
            - `median_session_duration` - Median session length in seconds
            - `total_session_duration` - Combined duration of all sessions
            - `min_session_duration` - Shortest session duration
            - `max_session_duration` - Longest session duration
            - `std_session_duration` - Standard deviation of session durations
            - `created_event_sum` - Total number of sessions where user created events
            - `viewed_event_sum` - Total number of sessions where user viewed events
            - `joined_event_sum` - Total number of sessions where user joined events
            - `invited_someone_sum` - Total number of sessions where user invited someone
            - `enabled_contacts_sum` - Total number of sessions where user enabled contacts
            - `scrolled_sum` - Total number of sessions where user scrolled
            - `visited_discover_sum` - Total number of sessions where user visited Discover
            - `started_quiz_sum` - Total number of sessions where user started quiz
            - `completed_quiz_sum` - Total number of sessions where user completed quiz
            - `total_scrolls` - Total scroll events across all sessions
            - `avg_scrolls_per_session` - Average scroll events per session
            - `max_scrolls_per_session` - Maximum scrolls in a single session
            - `total_autocaptures` - Total autocapture events across all sessions
            - `avg_autocaptures_per_session` - Average autocapture events per session
            - `max_autocaptures_per_session` - Maximum autocaptures in a single session
            - `total_screens` - Total unique screens viewed across all sessions
            - `avg_screens_per_session` - Average screens per session
            - `max_screens_per_session` - Maximum screens in a single session
            - `first_session_date` - Timestamp of user's first session
            - `last_session_date` - Timestamp of user's most recent session
            - `days_since_first_session` - Number of days between first and last session
            - `sessions_per_day` - Average sessions per day since first session
            - `engagement_score` - Percentage of sessions with key activity (created/joined/viewed events)
            - `fullName` - User's full name
            - `phoneNumber` - User's phone number
            - `username` - User's username
            - `email` - User's email address
            - `contactAccessGranted` - Boolean: contact access permission status
            - `businessUser` - Boolean flag: business user status
            - `createdAt` - User account creation timestamp
            - `city` - User's geographic city
            - `country` - User's geographic country
            - `etl_loaded_at` - ETL processing timestamp
                    """)
        
    available_columns = people_df.columns.tolist()
    default_columns = ['fullName', 'username', 'email', 'total_sessions', 'avg_session_duration', 
                      'engagement_score', 'country', 'city', 'businessUser', 'first_session_date']
    default_columns = [col for col in default_columns if col in available_columns]
    
    selected_columns = st.multiselect(
        "Choose columns",
        options=available_columns,
        default=default_columns
    )
    
    if selected_columns:
        st.dataframe(
            filtered_people[selected_columns],
            use_container_width=True,
            height=400
        )
        
        # Download option
        csv = filtered_people[selected_columns].to_csv(index=False)
        st.download_button(
            label=" Download filtered data as CSV",
            data=csv,
            file_name="people_data.csv",
            mime="text/csv"
        )
    else:
        st.warning("Please select at least one column to display")

# TAB 2: SESSIONS DATA
with tab2:
    st.header("Session Analytics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions", f"{len(sessions_df):,}")
    with col2:
        avg_duration = sessions_df['session_duration'].mean()
        st.metric("Avg Duration (s)", f"{avg_duration:.1f}")
    with col3:
        total_screens = sessions_df['screen_count'].sum()
        st.metric("Total Screens", f"{total_screens:,}")
    with col4:
        total_autocaptures = sessions_df['autocapture_count'].sum()
        st.metric("Total Autocaptures", f"{total_autocaptures:,}")
    
    st.subheader("Filter & Search")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        # Event filters
        st.markdown("**Events**")
            
        show_created = st.checkbox("Created Event", value=False)
        show_viewed = st.checkbox("Viewed Event", value=False)
        show_joined = st.checkbox("Joined Event", value=False)
        show_quiz = st.checkbox("Completed Quiz", value=False)
        show_discovered = st.checkbox("Visited Discover Page", value=False)
        
    with col2:
        # Country filter
        session_countries = ["All"] + sorted(sessions_df['country'].dropna().unique().tolist())
        selected_session_country = st.selectbox("Country", session_countries, key="session_country")
        
        # Date range
        if pd.notna(sessions_df['start_timestamp']).any():
            min_date = pd.to_datetime(sessions_df['start_timestamp']).min().date()
            max_date = pd.to_datetime(sessions_df['start_timestamp']).max().date()
            
            date_range = st.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
    
    # Apply filters
    filtered_sessions = sessions_df.copy()
    
    if show_created:
        filtered_sessions = filtered_sessions[filtered_sessions['created_event'] == True]
    if show_viewed:
        filtered_sessions = filtered_sessions[filtered_sessions['viewed_event'] == True]
    if show_joined:
        filtered_sessions = filtered_sessions[filtered_sessions['joined_event'] == True]
    if show_quiz:
        filtered_sessions = filtered_sessions[filtered_sessions['completed_quiz'] == True]
    if show_discovered:
        filtered_sessions = filtered_sessions[filtered_sessions['visited_discover'] == True]
    if selected_session_country != "All":
        filtered_sessions = filtered_sessions[filtered_sessions['country'] == selected_session_country]
    
    if 'date_range' in locals() and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (
            (pd.to_datetime(filtered_sessions['start_timestamp']).dt.date >= start_date) &
            (pd.to_datetime(filtered_sessions['start_timestamp']).dt.date <= end_date)
        )
        filtered_sessions = filtered_sessions[mask]
    
    st.info(f"Showing {len(filtered_sessions)} of {len(sessions_df)} sessions")
    
    # Column selection
    st.subheader("Select Columns to Display")
    with st.expander("Column Info"):
        st.markdown("""
                            **Columns:**
        - `session_id` - Unique session identifier (required)
        - `distinct_id` - PostHog distinct user identifier
        - `user_id` - Firebase user ID
        - `city` - User's geographic city
        - `country` - User's geographic country
        - `start_timestamp` - Session start time
        - `end_timestamp` - Session end time
        - `session_duration` - Length of session in seconds
        - `created_event` - Boolean flag: user created an event during session
        - `viewed_event` - Boolean flag: user viewed an event
        - `joined_event` - Boolean flag: user joined an event
        - `invited_someone` - Boolean flag: user sent an invite
        - `enabled_contacts` - Boolean flag: user enabled contact access
        - `scrolled` - Boolean flag: user scrolled during session
        - `visited_discover` - Boolean flag: user visited Discover page
        - `started_quiz` - Boolean flag: user started the quiz
        - `completed_quiz` - Boolean flag: user completed the quiz
        - `scroll_event_count` - Number of scroll events in session
        - `autocapture_count` - Number of events autocaptured by posthog SDK during session
        - `screen_count` - Number of unique screens visited
        - `fullName` - User's full name
        - `phoneNumber` - User's phone number
        - `username` - User's username
        - `email` - User's email address
        - `contactAccessGranted` - Boolean: contact access permission status
        - `businessUser` - Boolean flag: business user status
        - `createdAt` - User account creation timestamp (some users are null due to historical data issues)
        - `etl_loaded_at` - ETL processing timestamp
                    """)
        
    session_columns = sessions_df.columns.tolist()
    default_session_columns = ['session_id', 'fullName', 'username', 'start_timestamp', 'session_duration',
                               'screen_count', 'autocapture_count', 'scroll_event_count', 'country', 'city',
                               'created_event', 'viewed_event', 'joined_event', 'completed_quiz']
    default_session_columns = [col for col in default_session_columns if col in session_columns]
    
    selected_session_columns = st.multiselect(
        "Choose columns",
        options=session_columns,
        default=default_session_columns,
        key="session_columns"
    )
    
    if selected_session_columns:
        st.dataframe(
            filtered_sessions[selected_session_columns],
            use_container_width=True,
            height=400
        )
        
        # Download option
        csv = filtered_sessions[selected_session_columns].to_csv(index=False)
        st.download_button(
            label="📥 Download filtered data as CSV",
            data=csv,
            file_name="sessions_data.csv",
            mime="text/csv",
            key="download_sessions"
        )
    else:
        st.warning("Please select at least one column to display")

# TAB 3: CHURN DATA
with tab3:
    st.header("User Churn Analytics")
    
    col1, col2, col3, col4, spacer, col5, col6, col7 = st.columns([2, 0.75, 0.75, 0.75, 0.5,0.75, 0.75, 0.75])
    with col1:
        st.metric("Total Users", f"{len(churn_df.user_id.unique()):,}")
    with col2:
        app_churned = (churn_df['app_churn_state'] == 'churned').sum()
        st.metric("App Churned", f"{app_churned:,}")
    with col3:
        app_active = (churn_df['app_churn_state'] == 'active').sum()
        st.metric("App Active", f"{app_active:,}")
    with col4:
        app_reactivated = (churn_df['app_churn_state'] == 'reactivated').sum()
        st.metric("App Reactivated", f"{app_reactivated:,}")
    with col5:
        biz_churned = (churn_df['biz_churn_state'] == 'churned').sum()
        st.metric("Biz Churned", f"{biz_churned:,}")
    with col6:
        biz_active = (churn_df['biz_churn_state'] == 'active').sum()
        st.metric("Biz Active", f"{biz_active:,}")
    with col7:
        biz_reactivated = (churn_df['biz_churn_state'] == 'reactivated').sum()
        st.metric("Biz Reactivated", f"{biz_reactivated:,}")
    
    st.subheader("Filter & Search")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        # App churn state filter
        app_churn_states = ["All"] + sorted(churn_df['app_churn_state'].dropna().unique().tolist())
        selected_app_churn = st.selectbox("App Churn State", app_churn_states)
        
        # Biz churn state filter
        biz_churn_states = ["All"] + sorted(churn_df['biz_churn_state'].dropna().unique().tolist())
        selected_biz_churn = st.selectbox("Biz Churn State", biz_churn_states)
        
        # Days since last activity filter
        max_days_inactive = st.slider(
            "Max Days Since Last App Activity",
            min_value=0,
            max_value=int(churn_df['days_since_last_app_activity'].max()) if churn_df['days_since_last_app_activity'].max() > 0 else 365,
            value=int(churn_df['days_since_last_app_activity'].max()) if churn_df['days_since_last_app_activity'].max() > 0 else 365
        )

        max_days_biz_inactive = st.slider(
            "Max Days Since Last Biz Activity",
            min_value=0,
            max_value=int(churn_df['days_since_last_biz_activity'].max()) if churn_df['days_since_last_biz_activity'].max() > 0 else 365,
            value=int(churn_df['days_since_last_biz_activity'].max()) if churn_df['days_since_last_biz_activity'].max() > 0 else 365
        )
    
    with col2:
        # Times churned filter
        min_app_churns = st.slider(
            "Min App Times Churned",
            min_value=0,
            max_value=int(churn_df['app_times_churned'].max()),
            value=0
        )
        
        min_biz_churns = st.slider(
            "Min Biz Times Churned",
            min_value=0,
            max_value=int(churn_df['biz_times_churned'].max()),
            value=0
        )
        
        # Search by user ID, Fullname, or Email
        search_user = st.text_input("Search User ID, Fullname, or Email", key="churn_search")
    
    # Apply filters
    filtered_churn = churn_df.copy()
    
    if selected_app_churn != "All":
        filtered_churn = filtered_churn[filtered_churn['app_churn_state'] == selected_app_churn]
    
    if selected_biz_churn != "All":
        filtered_churn = filtered_churn[filtered_churn['biz_churn_state'] == selected_biz_churn]
    
    #need to make this conditional for users who never used the app
    if max_days_inactive < churn_df['days_since_last_app_activity'].max():
        filtered_churn = filtered_churn[filtered_churn['days_since_last_app_activity'] <= max_days_inactive]

    if max_days_biz_inactive < churn_df['days_since_last_biz_activity'].max():
        filtered_churn = filtered_churn[filtered_churn['days_since_last_biz_activity'] <= max_days_biz_inactive]
    
    #filtering on times churned
    filtered_churn = filtered_churn[filtered_churn['app_times_churned'] >= min_app_churns]
    filtered_churn = filtered_churn[filtered_churn['biz_times_churned'] >= min_biz_churns]
    
    if search_user:
        filtered_churn = filtered_churn[
            filtered_churn['user_id'].str.contains(search_user, case=False, na=False) |
            filtered_churn['fullName'].str.contains(search_user, case=False, na=False) |
            filtered_churn['email'].str.contains(search_user, case=False, na=False)
        ]
    
    st.info(f"Showing {len(filtered_churn)} of {len(churn_df)} users")
    
    # Column selection
    st.subheader("Select Columns to Display")

    with st.expander("Column Info"):
        st.markdown("""
                            **Columns:**
        - `user_id` - Firebase user ID
        - `app_churn_state` - Churn state for app usage: active, churned, reactivated, or never_active
            - App churn looks at if a user had any app interactions in the last 14 days
        - `app_churn_date` - Date when user churned from app (won't display if not in churned state)
        - `app_times_churned` - Number of times user has churned and returned (app)
        - `days_since_last_app_activity` - Days since last app interaction
        - `first_app_active_date` - Date of first app activity
        - `last_app_active_date` - Date of most recent app activity
        - `biz_churn_state` - Churn state for business activity: active, churned, reactivated, or never_active
            - Business churn looks at if a user created/joined an event in the last 14 days
        - `biz_churn_date` - Date when user churned from business activity (won't display if not in churned state)
        - `biz_times_churned` - Number of times user has churned and returned (business)
        - `days_since_last_biz_activity` - Days since last business activity
        - `first_biz_active_date` - Date of first business activity
        - `last_biz_active_date` - Date of most recent business activity
        - `total_events_created` - Lifetime count of events created
        - `total_events_attended` - Lifetime count of events attended
        - `total_app_interactions` - Lifetime count of app interactions
        - `etl_loaded_at` - ETL processing timestamp
                    """)
        

    churn_columns = churn_df.columns.tolist()
    default_churn_columns = ['user_id','fullName', 'email', 'app_churn_state', 'app_churn_date', 'app_times_churned',
                             'days_since_last_app_activity', 'last_app_active_date', 
                             'biz_churn_state', 'biz_churn_date', 'biz_times_churned']
    default_churn_columns = [col for col in default_churn_columns if col in churn_columns]
    
    selected_churn_columns = st.multiselect(
        "Choose columns",
        options=churn_columns,
        default=default_churn_columns,
        key="churn_columns"
    )
    
    if selected_churn_columns:
        st.dataframe(
            filtered_churn[selected_churn_columns],
            use_container_width=True,
            height=400
        )
        
        # Download option
        csv = filtered_churn[selected_churn_columns].to_csv(index=False)
        st.download_button(
            label="📥 Download filtered data as CSV",
            data=csv,
            file_name="churn_data.csv",
            mime="text/csv",
            key="download_churn"
        )
    else:
        st.warning("Please select at least one column to display")

st.markdown("---")
st.markdown("*Data refreshes every hour. Click 'Clear cache' here to force refresh.*")
st.button("Clear cache", on_click=st.cache_data.clear)
