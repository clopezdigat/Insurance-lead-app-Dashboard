import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz
import plotly.express as px

# --- BRANDING & UI CONFIGURATION ---
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ border-top: 8px solid #3b0710; }}
    
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

    div.stButton > button {{
        background-color: #3b0710;
        color: #D4AF37;
        border: 2px solid #D4AF37;
        border-radius: 5px;
        transition: all 0.3s ease;
    }}

    div.stButton > button:hover {{
        background-color: #D4AF37 !important;
        color: #3b0710 !important;
        border: 2px solid #3b0710;
    }}

    /* TARGETED STICKY SECTION - REMOVES EXTRA TOP BARS */
    div[data-testid="stVerticalBlock"] > div:has(> div.sticky-anchor) {{
        position: sticky;
        top: -1px; 
        z-index: 1000;
        background-color: white;
        border-top: 2px solid #D4AF37;
        border-bottom: 2px solid #D4AF37;
        padding: 15px 0px;
        margin: 10px 0px 20px 0px;
    }}

    [data-testid="stExpander"] {{ border: 1px solid #D4AF37; border-radius: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- GLOBAL UTILITIES ---
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
        sync_time = datetime.now(tz).strftime("%H:%M")
        return prod_df, rec_df, sync_time
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), "00:00"

def get_filtered_data(df, timeframe_label):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0, df
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp'], errors='coerce')
    temp_df = temp_df.dropna(subset=['Timestamp'])
    now = datetime.now()
    mapping = {
        "1 hr": timedelta(hours=1), "12 hr": timedelta(hours=12), "24 hr": timedelta(days=1),
        "1 week": timedelta(weeks=1), "1 month": timedelta(days=30), "All Time": None
    }
    duration = mapping.get(timeframe_label)
    if timeframe_label == "All Time":
        return len(temp_df), 0, temp_df
    current_df = temp_df[temp_df['Timestamp'] > (now - duration)]
    prev_start = now - (duration * 2)
    prev_end = now - duration
    prev_count = len(temp_df[(temp_df['Timestamp'] > prev_start) & (temp_df['Timestamp'] <= prev_end)])
    return len(current_df), (len(current_df) - prev_count), current_df

def render_market_insights(df, timeframe_label):
    with st.expander("📈 Strategic Analytics & Market Trends", expanded=True):
        v1, v2, v3 = st.columns(3)
        with v1:
            st.write("**Activity Trend**")
            if not df.empty:
                rule = 'H' if timeframe_label in ["1 hr", "12 hr", "24 hr"] else 'D'
                trend = df.set_index('Timestamp').resample(rule).size().reset_index(name='Leads')
                fig = px.line(trend, x='Timestamp', y='Leads', color_discrete_sequence=['#3b0710'])
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                fig.update_xaxes(tickformat="%H:%M" if rule == 'H' else "%b %d")
                st.plotly_chart(fig, use_container_width=True)
        with v2:
            st.write("**Market Share**")
            loc_col = next((c for c in ['State', 'City'] if c in df.columns), None)
            if loc_col and not df.empty:
                loc_data = df[loc_col].replace('', 'N/A').fillna('N/A').value_counts().reset_index()
                fig = px.pie(loc_data, values='count', names=loc_col, hole=0.4, color_discrete_sequence=['#3b0710', '#D4AF37', '#7d111c'])
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        with v3:
            st.write("**Top Interests**")
            if 'Interest Selected' in df.columns:
                int_data = df['Interest Selected'].value_counts().head(3).reset_index()
                if not int_data.empty:
                    fig = px.bar(int_data, x='count', y='Interest Selected', orientation='h', color_discrete_sequence=['#D4AF37'])
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0), xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("No data.")
            else: st.caption("Column missing.")

def process_table(df, s_query, s_filter):
    if df.empty: return df
    f = df.copy()
    if 'Timestamp' in f.columns:
        f['Timestamp'] = pd.to_datetime(f['Timestamp'], errors='coerce')
        now = datetime.now()
        f['Days Idle'] = (now - f['Timestamp']).dt.days
        f['Days Idle'] = f['Days Idle'].apply(lambda x: max(x, 0) if pd.notnull(x) else 0)
    
    if s_query: 
        f = f[f['Full Name'].str.contains(s_query, case=False, na=False)]
    if s_filter != "All": 
        f = f[f['Status'] == s_filter]
    
    if 'Email Address' in f.columns:
        f['📧'] = f['Email Address'].apply(lambda x: f"mailto:{x}" if x else "")
    if 'Phone Number' in f.columns:
        f['📞'] = f['Phone Number'].apply(lambda x: f"tel:{x}" if x else "")
    
    cols = list(f.columns)
    base = [c for c in cols if c not in ['📧', '📞', 'Days Idle']]
    
    if 'Timestamp' in base:
        base.insert(base.index('Timestamp'), 'Days Idle')
    if 'Email Address' in base:
        base.insert(base.index('Email Address') + 1, '📧')
    if 'Phone Number' in base:
        base.insert(base.index('Phone Number') + 1, '📞')
        
    return f[base]

table_config = {
    "Email Address": st.column_config.TextColumn("Email Address"),
    "📧": st.column_config.LinkColumn(" ", display_text="Email"),
    "Phone Number": st.column_config.TextColumn("Phone Number"),
    "📞": st.column_config.LinkColumn(" ", display_text="Call"),
    "Days Idle": st.column_config.NumberColumn("Days Idle", help="Days since lead was created", format="%d days"),
}

# --- DASHBOARD EXECUTION ---
try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    
    if 'search_query' not in st.session_state: st.session_state.search_query = ""
    if 'status_filter' not in st.session_state: st.session_state.status_filter = "All"

    with st.sidebar:
        st.title("🛡️ Admin Panel")
        timeframe = st.selectbox("Performance Period:", ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "All Time"], index=3)
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Last Sync: {last_sync} CST")
        st.markdown("---")
        st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
        st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")

    st.markdown(f'<div class="hero-box"><h1>📋 Executive Oversight</h1><p>Internal Lead Management System | Last Sync: {last_sync}</p></div>', unsafe_allow_html=True)

    p_count, p_delta, filtered_prod = get_filtered_data(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_filtered_data(raw_rec_df, timeframe)
    
    m1, m2 = st.columns(2)
    m1.metric(f"Product Leads", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m2.metric(f"Recruits", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # --- STICKY SECTION ---
    with st.container():
        st.markdown('<div class="sticky-anchor"></div>', unsafe_allow_html=True)
        s1, s2, s3 = st.columns([2, 1, 0.5])
        with s1:
            search_query = st.text_input("Search Main Table:", value=st.session_state.search_query, placeholder="Name...", key="s_input")
        with s2:
            status_list = ["All", "New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
            status_filter = st.selectbox("Status Filter:", status_list, index=status_list.index(st.session_state.status_filter), key="st_select")
        with s3:
            st.write(" ") 
            if st.button("Reset"):
                st.session_state.search_query = ""
                st.session_state.status_filter = "All"
                st.rerun()

    t1, t2 = st.tabs(["🛍️ Products", "🤝 Recruits"])
    with t1:
        render_market_insights(filtered_prod, timeframe)
        st.dataframe(process_table(raw_prod_df, search_query, status_filter), use_container_width=True, hide_index=True, column_config=table_config)
    with t2:
        render_market_insights(filtered_rec, timeframe)
        st.dataframe(process_table(raw_rec_df, search_query, status_filter), use_container_width=True, hide_index=True, column_config=table_config)

    # --- UPDATE FORM ---
    st.markdown("---")
    st.subheader("📝 Update Lead")
    u1, u2 = st.columns([1, 2])
    with u1:
        target_ws = st.radio("Sheet to Update:", ["Product", "Recruitment"], horizontal=True)
        active_df = raw_prod_df if target_ws == "Product" else raw_rec_df
        if not active_df.empty:
            lead_options = active_df.apply(lambda x: f"{x['Full Name']} ({x['Email Address']})", axis=1).tolist()
            selected_lead_display = st.selectbox("Find Lead (Type Name or Email):", lead_options)
            selected_email = selected_lead_display.split('(')[-1].strip(')')
        else: selected_email = None

    with u2:
        if selected_email:
            row = active_df[active_df['Email Address'] == selected_email].iloc[0]
            cs1, cs2 = st.columns(2)
            with cs1:
                st_opts = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
                curr_st = row.get('Status', 'New')
                new_st = st.selectbox("Update Status:", st_opts, index=st_opts.index(curr_st) if curr_st in st_opts else 0)
            with cs2:
                new_note = st.text_area("Edit Notes:", value=str(row.get('Notes', '')), height=68)
            if st.button("Save Changes to Google Sheet", use_container_width=True):
                gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
                ws = gc.open("Lead Manager").worksheet(target_ws)
                cell = ws.find(selected_email)
                headers = [h.strip() for h in ws.row_values(1)]
                ws.update_cell(cell.row, headers.index("Status") + 1, new_st)
                ws.update_cell(cell.row, headers.index("Notes") + 1, new_note)
                st.success(f"Changes saved for {row['Full Name']}!")
                st.cache_data.clear()
                st.rerun()

except Exception as e:
    st.error(f"Error: {e}")
