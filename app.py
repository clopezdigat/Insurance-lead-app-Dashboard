import streamlit as st
import pd
import gspread
from datetime import datetime, timedelta
import pytz
import plotly.express as px

# --- BRANDING & UI CONFIGURATION ---
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

# Custom CSS for Hero Box, Button Inversion, and Sticky Search
st.markdown(f"""
    <style>
    /* Top Gold Bar accent */
    .stApp {{ border-top: 8px solid #D4AF37; }}
    
    /* The "Hero Box" Title Section */
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

    /* Button Styling & Hover Inversion */
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

    /* Sticky Search Bar Logic */
    /* This pins the search container to the top just under the gold bar */
    div[data-testid="stVerticalBlock"] > div:has(div.sticky-search-wrapper) {{
        position: sticky;
        top: 0rem;
        background-color: white;
        z-index: 999;
        padding-top: 10px;
        padding-bottom: 10px;
        border-bottom: 2px solid #f0f2f6;
    }}

    /* Standard Elements */
    [data-testid="stExpander"] {{ border: 1px solid #D4AF37; border-radius: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- DATA ENGINE ---
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
    
    current_df = temp_df[temp_df['Timestamp'] > (now - duration)]
    prev_start = now - (duration * 2)
    prev_end = now - duration
    prev_count = len(temp_df[(temp_df['Timestamp'] > prev_start) & (temp_df['Timestamp'] <= prev_end)])
    
    return len(current_df), (len(current_df) - prev_count), current_df

# --- DASHBOARD EXECUTION ---
try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    
    with st.sidebar:
        st.title("🛡️ Admin Panel")
        timeframe = st.selectbox(
            "Performance Period:", 
            ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "6 month", "1 year", "All Time"], 
            index=3
        )
        st.markdown("---")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Last Sync: {last_sync} CST")

    # Hero Box Header
    st.markdown(f"""
        <div class="hero-box">
            <h1>📋 Executive Oversight</h1>
            <p>Secure. Professional. Trusted. | Internal Lead Management System</p>
        </div>
    """, unsafe_allow_html=True)

    # Process Metrics & Chart Data
    p_count, p_delta, filtered_prod = get_filtered_data(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_filtered_data(raw_rec_df, timeframe)
    
    # Top-Level Metrics
    m1, m2 = st.columns(2)
    m1.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m2.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # Collapsible Analytics Section
    with st.expander("📈 Strategic Analytics & Market Trends", expanded=False):
        v1, v2, v3 = st.columns(3)
        combined = pd.concat([filtered_prod.assign(Cat='Product'), filtered_rec.assign(Cat='Recruit')])

        with v1:
            st.write("**Activity Trend**")
            if not combined.empty:
                rule = 'H' if timeframe in ["1 hr", "12 hr", "24 hr"] else 'D'
                trend = combined.set_index('Timestamp').resample(rule).size().reset_index(name='Leads')
                fig = px.line(trend, x='Timestamp', y='Leads', color_discrete_sequence=['#3b0710'])
                fig.update_layout(height=240, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

        with v2:
            st.write("**Market Share**")
            loc_col = 'State' if 'State' in filtered_prod.columns else ('City' if 'City' in filtered_prod.columns else None)
            if loc_col and not filtered_prod.empty:
                loc_data = filtered_prod[loc_col].value_counts().reset_index()
                fig = px.pie(loc_data, values='count', names=loc_col, hole=0.4, color_discrete_sequence=['#3b0710', '#D4AF37', '#7d111c'])
                fig.update_layout(height=240, margin=dict(l=0,r=0,t=0,b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with v3:
            st.write("**Top Interests**")
            int_col = 'Product Interest' if 'Product Interest' in filtered_prod.columns else ('Interest' if 'Interest' in filtered_prod.columns else None)
            if int_col and not filtered_prod.empty:
                int_data = filtered_prod[int_col].value_counts().reset_index()
                fig = px.bar(int_data, x='count', y=int_col, orientation='h', color_discrete_sequence=['#D4AF37'])
                fig.update_layout(height=240, margin=dict(l=0,r=0,t=0,b=0), xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

    # --- STICKY LEAD INVENTORY & SEARCH ---
    # We wrap this in a container to trigger the CSS sticky logic
    with st.container():
        st.markdown('<div class="sticky-search-wrapper"></div>', unsafe_allow_html=True)
        st.markdown("### 🔍 Lead Inventory")
        s1, s2 = st.columns([2, 1])
        with s1:
            search_query = st.text_input("Search Leads:", placeholder="Search by name...")
        with s2:
            status_filter = st.selectbox("Status Filter:", ["All", "New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"])

    def process_table(df):
        if df.empty: return df
        f = df.copy()
        if search_query:
            f = f[f['Full Name'].str.contains(search_query, case=False, na=False)]
        if status_filter != "All":
            f = f[f['Status'] == status_filter]
        
        if 'Email Address' in f.columns:
            f['📧'] = f['Email Address'].apply(lambda x: f"mailto:{x}" if x else "")
        if 'Phone Number' in f.columns:
            f['📞'] = f['Phone Number'].apply(lambda x: f"tel:{x}" if x else "")
            
        cols = list(f.columns)
        base = [c for c in cols if c not in ['📧', '📞']]
        if 'Email Address' in base: base.insert(base.index('Email Address') + 1, '📧')
        if 'Phone Number' in base: base.insert(base.index('Phone Number') + 1, '📞')
        return f[base]

    table_config = {
        "Email Address": st.column_config.TextColumn("Email Address"),
        "📧": st.column_config.LinkColumn(" ", display_text="Email"),
        "Phone Number": st.column_config.TextColumn("Phone Number"),
        "📞": st.column_config.LinkColumn(" ", display_text="Call"),
    }

    t1, t2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])
    with t1:
        st.dataframe(process_table(raw_prod_df), use_container_width=True, hide_index=True, column_config=table_config)
    with t2:
        st.dataframe(process_table(raw_rec_df), use_container_width=True, hide_index=True, column_config=table_config)

    # --- GOOGLE SHEETS UPDATE FORM ---
    st.markdown("---")
    st.subheader("📝 Update Contact Progress")
    u1, u2 = st.columns([1, 2])
    with u1:
        target_ws = st.radio("Update Sheet:", ["Product", "Recruitment"], horizontal=True)
        active_df = raw_prod_df if target_ws == "Product" else raw_rec_df
        if not active_df.empty:
            selected_lead = st.selectbox("Target Lead (Email):", active_df['Email Address'].unique())
        else:
            selected_lead = None

    with u2:
        if selected_lead:
            row_data = active_df[active_df['Email Address'] == selected_lead].iloc[0]
            cs1, cs2 = st.columns(2)
            with cs1:
                st_opts = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
                current_st = row_data.get('Status', 'New')
                new_st = st.selectbox("Set Status:", st_opts, index=st_opts.index(current_st) if current_st in st_opts else 0)
            with cs2:
                new_note = st.text_area("Update Notes:", value=str(row_data.get('Notes', '')), height=68)
            
            # Button spans the width of the update inputs (u2)
            if st.button("Save Changes to Google Sheet", use_container_width=True):
                gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
                ws = gc.open("Lead Manager").worksheet(target_ws)
                cell = ws.find(selected_lead)
                headers = [h.strip() for h in ws.row_values(1)]
                ws.update_cell(cell.row, headers.index("Status") + 1, new_st)
                ws.update_cell(cell.row, headers.index("Notes") + 1, new_note)
                st.success(f"Successfully updated {selected_lead}")
                st.cache_data.clear()
                st.rerun()

    with st.sidebar:
        st.markdown("---")
        st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
        st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")

except Exception as e:
    st.error(f"Operational Error: {e}")
