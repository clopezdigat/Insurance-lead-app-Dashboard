import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz
import plotly.express as px

# Branding & UI
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

# Custom CSS for Burgundy (#3b0710) & Gold (#D4AF37)
st.markdown(f"""
    <style>
    .stApp {{ border-top: 8px solid #D4AF37; }}
    h1, h2, h3 {{ color: #3b0710 !important; font-family: 'Segoe UI', sans-serif; }}
    div[data-testid="stMetricValue"] {{ color: #3b0710; }}
    [data-testid="stExpander"] {{ border: 1px solid #D4AF37; border-radius: 5px; background-color: #fdfaf3; }}
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
        
        tz = pytz.timezone('US/Central')
        sync_time = datetime.now(tz).strftime("%I:%M %p")
        return prod_df, rec_df, sync_time
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Error"

def get_delta_metrics(df, timeframe_label):
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
    
    current_df = temp_df[temp_df['Timestamp'] > (now - duration)]
    prev_count = len(temp_df[(temp_df['Timestamp'] > (now - duration*2)) & (temp_df['Timestamp'] <= (now - duration))])
    
    return len(current_df), (len(current_df) - prev_count), current_df

try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    
    with st.sidebar:
        st.title("🛡️ Admin Panel")
        timeframe = st.selectbox("View Strategy For:", ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "6 month", "1 year", "All Time"], index=3)
        st.markdown("---")
        if st.button("🔄 Reload Data"):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Last Sync: {last_sync} CST")

    st.title("📋 Executive Oversight")

    # Top Metrics always visible
    p_count, p_delta, filtered_prod = get_delta_metrics(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_delta_metrics(raw_rec_df, timeframe)
    
    m1, m2 = st.columns(2)
    m1.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m2.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # --- COLLAPSIBLE ANALYTICS SECTION ---
    with st.expander("📈 View Strategic Visuals & Analytics", expanded=False):
        v1, v2, v3 = st.columns(3)

        with v1:
            st.write("**Daily Lead Flow**")
            combined = pd.concat([filtered_prod.assign(Category='Product'), filtered_rec.assign(Category='Recruit')])
            if not combined.empty:
                trend = combined.copy()
                trend['Date'] = trend['Timestamp'].dt.date
                trend_grouped = trend.groupby('Date').size().reset_index(name='Count')
                fig = px.bar(trend_grouped, x='Date', y='Count', color_discrete_sequence=['#3b0710'])
                fig.update_layout(height=250, margin=dict(l=10,r=10,t=10,b=10), xaxis_title=None, yaxis_title=None, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

        with v2:
            st.write("**Market Share**")
            loc_col = 'State' if 'State' in filtered_prod.columns else ('City' if 'City' in filtered_prod.columns else None)
            if loc_col and not filtered_prod.empty:
                loc_data = filtered_prod[loc_col].value_counts().reset_index()
                loc_data.columns = [loc_col, 'Leads']
                fig = px.pie(loc_data, values='Leads', names=loc_col, hole=0.5, color_discrete_sequence=['#3b0710', '#D4AF37', '#a67c00', '#5c121b'])
                fig.update_layout(height=250, margin=dict(l=10,r=10,t=10,b=10), showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

        with v3:
            st.write("**Top Interests**")
            int_col = 'Product Interest' if 'Product Interest' in filtered_prod.columns else ('Interest' if 'Interest' in filtered_prod.columns else None)
            if int_col and not filtered_prod.empty:
                int_data = filtered_prod[int_col].value_counts().reset_index()
                int_data.columns = [int_col, 'Count']
                fig = px.bar(int_data, x='Count', y=int_col, orientation='h', color_discrete_sequence=['#D4AF37'])
                fig.update_layout(height=250, margin=dict(l=10,r=10,t=10,b=10), xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

    # --- MAIN TABLE SECTION ---
    st.markdown("### 🔍 Lead Management")
    # ... Rest of your search and table code here ...

except Exception as e:
    st.error(f"Error: {e}")
