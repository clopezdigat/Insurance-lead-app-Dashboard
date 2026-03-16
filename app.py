import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz

# Branding & UI (Must be the first Streamlit command)
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { border-top: 6px solid #D4AF37; }
    h1, h2 { color: #3b0710; }
    div[data-testid="stMetricValue"] { color: #3b0710; }
    </style>
""", unsafe_allow_html=True)

# Data Connection
@st.cache_data(ttl=600) # Cache for 10 mins to save API calls
def get_data():
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    sh = gc.open("Lead Manager")
    
    prod_df = pd.DataFrame(sh.worksheet("Product").get_all_records())
    rec_df = pd.DataFrame(sh.worksheet("Recruitment").get_all_records())
    return prod_df, rec_df

# Helper Function for Metrics
def get_delta_metrics(df):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0
    
    # Convert Column to datetime and strip timezone for comparison
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize(None)
    
    # Get current time and strip timezone to match the column
    tz = pytz.timezone('US/Central')
    now = datetime.now(tz).replace(tzinfo=None) # Make it naive to match Pandas
    
    yesterday = now - timedelta(days=1)
    day_before = now - timedelta(days=2)
    
    # Perform the comparison
    current_leads = len(df[df['Timestamp'] > yesterday])
    previous_leads = len(df[(df['Timestamp'] > day_before) & (df['Timestamp'] <= yesterday)])
    
    return current_leads, (current_leads - previous_leads)

# Load Data
try:
    prod_df, rec_df = get_data()
    
    # Calculate Metrics
    p_count, p_delta = get_delta_metrics(prod_df)
    r_count, r_delta = get_delta_metrics(rec_df)

    # Dashboard Layout
    st.title("📋 Executive Oversight")

    col1, col2 = st.columns(2)
    col1.metric("New Product Leads (24h)", p_count, delta=int(p_delta))
    col2.metric("New Recruits (24h)", r_count, delta=int(r_delta))

    # Shift Indeces
    prod_df.index = prod_df.index + 1
    rec_df.index = rec_df.index + 1

    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Pipeline"])

    with tab1:
        st.dataframe(prod_df, use_container_width=True)
    with tab2:
        st.dataframe(rec_df, use_container_width=True)

except Exception as e:
    st.error(f"Error loading data: {e}")

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🔗 Digital Suite")
    st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
    st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()
