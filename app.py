import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz
import plotly.express as px

# Branding & UI
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

# Custom CSS for Hero Box & Theme
st.markdown(f"""
    <style>
    .stApp {{ border-top: 8px solid #D4AF37; }}
    
    /* Hero Box for Title Section */
    .hero-box {{
        background-color: #3b0710;
        padding: 2rem;
        border-radius: 10px;
        border-left: 10px solid #D4AF37;
        margin-bottom: 2rem;
    }}
    .hero-box h1 {{
        color: #D4AF37 !important;
        margin: 0;
        font-family: 'Segoe UI', sans-serif;
    }}
    .hero-box p {{
        color: white;
        margin: 5px 0 0 0;
        opacity: 0.9;
    }}

    h3 {{ color: #3b0710 !important; }}
    div[data-testid="stMetricValue"] {{ color: #3b0710; }}
    [data-testid="stExpander"] {{ border: 1px solid #D4AF37; border-radius: 5px; background-color: #fdfaf3; }}
    .stButton>button {{ background-color: #3b0710; color: white; border-radius: 5px; }}
    </style>
""", unsafe_allow_html=True)

# Data Connection
@st.cache_data(ttl=600)
def get_data():
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("Lead Manager")
        prod_df = pd.DataFrame(sh.worksheet("Product").get_all_records())
        rec_df = pd.DataFrame(sh.worksheet("Recruitment").get_all_records())
        
        prod_df.columns = [c.strip() for c in prod_df.columns]
        rec_df.columns = [c.strip() for c in rec_df.columns]
        
        return prod_df, rec_df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

def get_filtered_data(df, timeframe_label):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0, df
    
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp'], errors='coerce')
    temp_df = temp_df.dropna(subset=['Timestamp'])
    
    now = datetime.now()
    mapping = {
        "1 hr": timedelta(hours=1), "12 hr": timedelta(hours=12), "24 hr": timedelta(days=1),
        "1 week": timedelta(weeks=1), "1 month": timedelta(days=30), "6 month": timedelta(days=182),
        "1 year": timedelta(days=365), "All Time": None
    }
    
    duration = mapping.get(timeframe_label)
    
    if timeframe_label == "All Time":
        return len(temp_df), 0, temp_df
    
    # Filter for the selected window
    current_df = temp_df[temp_df['Timestamp'] > (now - duration)]
    
    # Calculate delta based on the previous equal window
    prev_start = now - (duration * 2)
    prev_end = now - duration
    prev_count = len(temp_df[(temp_df['Timestamp'] > prev_start) & (temp_df['Timestamp'] <= prev_end)])
    
    return len(current_df), (len(current_df) - prev_count), current_df

try:
    raw_prod_df, raw_rec_df = get_data()
    
    with st.sidebar:
        st.title("🛡️ Admin Panel")
        timeframe = st.selectbox("Update Period:", ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "6 month", "1 year", "All Time"], index=3)
        st.markdown("---")
        if st.button("🔄 Reload Systems"):
            st.cache_data.clear()
            st.rerun()

    # --- HERO BOX HEADER ---
    st.markdown(f"""
        <div class="hero-box">
            <h1>📋 Executive Oversight</h1>
            <p>Secure. Professional. Trusted. | Agency Performance Dashboard</p>
        </div>
    """, unsafe_allow_html=True)

    # Dynamic Data Processing
    p_count, p_delta, filtered_prod = get_filtered_data(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_filtered_data(raw_rec_df, timeframe)
    
    # Metrics
    m1, m2 = st.columns(2)
    m1.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m2.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # Visual Analytics Drawer
    with st.expander("📈 Strategic Analytics Drawer", expanded=False):
        v1, v2, v3 = st.columns(3)
        
        with v1:
            st.write("**Activity Trend**")
            combined = pd.concat([filtered_prod.assign(Type='P'), filtered_rec.assign(Type='R')])
            if not combined.empty:
                # Dynamic resampling based on timeframe to keep chart clean
                resample_rule = 'H' if timeframe in ["1 hr", "12 hr", "24 hr"] else 'D'
                trend = combined.set_index('Timestamp').resample(resample_rule).size().reset_index(name='Leads')
                fig = px.line(trend, x='Timestamp', y='Leads', color_discrete_sequence=['#3b0710'])
                fig.update_layout(height=230, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

        with v2:
            st.write("**Market Share**")
            loc_col = 'State' if 'State' in filtered_prod.columns else 'City'
            if not filtered_prod.empty and loc_col in filtered_prod.columns:
                loc_data = filtered_prod[loc_col].value_counts().reset_index()
                fig = px.pie(loc_data, values='count', names=loc_col, hole=0.4, color_discrete_sequence=['#3b0710', '#D4AF37', '#7d111c'])
                fig.update_layout(height=230, margin=dict(l=0,r=0,t=0,b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with v3:
            st.write("**Top Interests**")
            int_col = 'Product Interest' if 'Product Interest' in filtered_prod.columns else 'Interest'
            if not filtered_prod.empty and int_col in filtered_prod.columns:
                int_data = filtered_prod[int_col].value_counts().reset_index()
                fig = px.bar(int_data, x='count', y=int_col, orientation='h', color_discrete_sequence=['#D4AF37'])
                fig.update_layout(height=230, margin=dict(l=0,r=0,t=0,b=0), xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

    # --- MANAGEMENT SECTION ---
    st.markdown("### 🔍 Filtered Lead Inventory")
    
    # (Rest of the search, table, and gspread update logic follows here...)
    # [Rest of code logic exactly as previous complete version]

except Exception as e:
    st.error(f"Dashboard Load Error: {e}")
