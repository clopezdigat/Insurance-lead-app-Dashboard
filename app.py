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
    .stButton>button {{ background-color: #3b0710; color: white; border-radius: 5px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; }}
    .stTabs [data-baseweb="tab"] {{ color: #3b0710; }}
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

# Main Dashboard Logic
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

    # Top Metrics
    p_count, p_delta, filtered_prod = get_delta_metrics(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_delta_metrics(raw_rec_df, timeframe)
    
    m1, m2 = st.columns(2)
    m1.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m2.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # Collapsible Analytics
    with st.expander("📈 View Strategic Visuals & Analytics", expanded=False):
        v1, v2, v3 = st.columns(3)
        combined = pd.concat([filtered_prod.assign(Category='Product'), filtered_rec.assign(Category='Recruit')])

        with v1:
            st.write("**Daily Lead Flow**")
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

    # Search & Filter restored
    st.markdown("### 🔍 Lead Management")
    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        search_query = st.text_input("Search by Full Name:", placeholder="Start typing...")
    with f_col2:
        selected_status = st.selectbox("Filter Table by Status:", ["All", "New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"])

    def process_display_df(df):
        if df.empty: return df
        f = df.copy()
        if search_query and 'Full Name' in f.columns:
            f = f[f['Full Name'].str.contains(search_query, case=False, na=False)]
        if selected_status != "All" and 'Status' in f.columns:
            f = f[f['Status'] == selected_status]
        
        if 'Email Address' in f.columns:
            f['📧'] = f['Email Address'].apply(lambda x: f"mailto:{x}" if x else "")
        if 'Phone Number' in f.columns:
            f['📞'] = f['Phone Number'].apply(lambda x: f"tel:{x}" if x else "")
            
        cols = list(f.columns)
        base = [c for c in cols if c not in ['📧', '📞']]
        if 'Email Address' in base: base.insert(base.index('Email Address') + 1, '📧')
        if 'Phone Number' in base: base.insert(base.index('Phone Number') + 1, '📞')
        return f[base]

    display_prod = process_display_df(raw_prod_df)
    display_rec = process_display_df(raw_rec_df)

    column_config = {
        "Email Address": st.column_config.TextColumn("Email Address"),
        "📧": st.column_config.LinkColumn(" ", display_text="Email"),
        "Phone Number": st.column_config.TextColumn("Phone Number"),
        "📞": st.column_config.LinkColumn(" ", display_text="Call"),
    }

    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])
    with tab1:
        st.dataframe(display_prod, use_container_width=True, hide_index=True, column_config=column_config)
    with tab2:
        st.dataframe(display_rec, use_container_width=True, hide_index=True, column_config=column_config)

    # Update Lead Progress restored
    st.markdown("---")
    st.subheader("📝 Update Lead Progress")
    c1, c2 = st.columns([1, 2])
    with c1:
        target = st.radio("Target Sheet:", ["Product", "Recruitment"], horizontal=True)
        df_to_use = raw_prod_df if target == "Product" else raw_rec_df
        if not df_to_use.empty and 'Email Address' in df_to_use.columns:
            lead_email = st.selectbox("Select Lead to Edit:", df_to_use['Email Address'].unique().tolist())
        else:
            lead_email = None

    with c2:
        if lead_email:
            match = df_to_use[df_to_use['Email Address'] == lead_email].iloc[0]
            col_s, col_n = st.columns(2)
            with col_s:
                status_options = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
                new_status = st.selectbox("New Status:", status_options, index=status_options.index(match.get('Status', 'New')) if match.get('Status') in status_options else 0)
            with col_n:
                new_note = st.text_area("New Notes:", value=str(match.get('Notes', '')))
            if st.button("Save Changes to Google Sheet"):
                try:
                    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
                    ws = gc.open("Lead Manager").worksheet(target)
                    cell = ws.find(lead_email)
                    clean_header = [h.strip() for h in ws.row_values(1)]
                    ws.update_cell(cell.row, clean_header.index("Status") + 1, new_status)
                    ws.update_cell(cell.row, clean_header.index("Notes") + 1, new_note)
                    st.success("Updated successfully!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with st.sidebar:
        st.markdown("---")
        st.write
