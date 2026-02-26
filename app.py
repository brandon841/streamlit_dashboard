import streamlit as st
from utilities import init_bigquery_client
from google.cloud import bigquery
import os
import pandas as pd
import numpy as np
import json

# Page configuration
st.set_page_config(
    page_title="PostHog Analytics Dashboard",
    page_icon="",
    layout="wide"
)

st.title("PostHog Analytics Dashboard")
st.markdown("Interactive exploration of aggregated user and session data")

# Cache the data loading to avoid repeated queries
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Load data from BigQuery"""
    bq = init_bigquery_client()
    
    with st.spinner("Loading people data..."):
        people_query = """
            SELECT * FROM `etl-testing-478716.posthog_aggregated_prod.people_aggregated`
        """
        people_df = bq.query(people_query).to_dataframe()
    
    with st.spinner("Loading sessions data..."):
        sessions_query = """
            SELECT * FROM `etl-testing-478716.posthog_aggregated_prod.sessions_aggregated`
        """
        sessions_df = bq.query(sessions_query).to_dataframe()
    
    return people_df, sessions_df

# Load data
try:
    people_df, sessions_df = load_data()
    st.success(f"Data loaded successfully! {len(people_df)} users, {len(sessions_df)} sessions")
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

# Create tabs for different views
tab1, tab2 = st.tabs(["People Data", "Sessions Data"])

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
    with st.expander("Column Calculation Info"):
        st.write("Engagement score is calculated as a proportion of key events (joined event, created event, viewed event, scrolled) / total sessions")
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

# # TAB 3: QUICK INSIGHTS
# with tab3:
#     st.header("Quick Insights")
    
#     col1, col2 = st.columns(2)
    
#     with col1:
#         st.subheader("📊 User Engagement Distribution")
        
#         # Engagement score histogram
#         engagement_data = people_df['engagement_score'].dropna()
#         if len(engagement_data) > 0:
#             st.bar_chart(engagement_data.value_counts().sort_index())
#         else:
#             st.info("No engagement score data available")
        
#         st.subheader("🌍 Top Countries")
#         country_counts = people_df['country'].value_counts().head(10)
#         st.bar_chart(country_counts)
        
#         st.subheader("📅 User Registration Trend")
#         if pd.notna(people_df['createdAt']).any():
#             people_df['createdAt_date'] = pd.to_datetime(people_df['createdAt']).dt.date
#             daily_signups = people_df['createdAt_date'].value_counts().sort_index()
#             st.line_chart(daily_signups)
#         else:
#             st.info("No creation date data available")
    
#     with col2:
#         st.subheader("🎯 Event Summary")
        
#         event_columns = [
#             'created_event_sum', 'viewed_event_sum', 'joined_event_sum',
#             'invited_someone_sum', 'enabled_contacts_sum', 'scrolled_sum',
#             'visited_discover_sum', 'started_quiz_sum', 'completed_quiz_sum'
#         ]
        
#         event_data = {}
#         for col in event_columns:
#             if col in people_df.columns:
#                 event_name = col.replace('_sum', '').replace('_', ' ').title()
#                 event_data[event_name] = people_df[col].sum()
        
#         if event_data:
#             event_series = pd.Series(event_data)
#             st.bar_chart(event_series)
#         else:
#             st.info("No event data available")
        
#         st.subheader("⏱️ Session Duration Stats")
#         duration_stats = {
#             'Mean': sessions_df['session_duration'].mean(),
#             'Median': sessions_df['session_duration'].median(),
#             'Max': sessions_df['session_duration'].max(),
#             'Min': sessions_df['session_duration'].min()
#         }
        
#         for stat, value in duration_stats.items():
#             st.metric(stat, f"{value:.2f}s")
        
#         st.subheader("👤 Business vs Personal Users")
#         user_type_counts = people_df['businessUser'].value_counts()
#         user_type_df = pd.DataFrame({
#             'Type': ['Personal', 'Business'],
#             'Count': [
#                 user_type_counts.get(False, 0),
#                 user_type_counts.get(True, 0)
#             ]
#         })
#         st.bar_chart(user_type_df.set_index('Type'))

st.markdown("---")
st.markdown("*Data refreshes every hour. Click 'Clear cache' here to force refresh.*")
st.button("Clear cache", on_click=st.cache_data.clear)
