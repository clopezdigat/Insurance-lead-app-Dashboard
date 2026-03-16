import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz

# Branding & UI
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { border-top: 6px solid #D4AF37; }
    h1, h2 { color: #3b0710; }
    div[data-testid="stMetricValue"] { color: #3b0710; }
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

# Updated Metric Logic for Custom Timeframes
def get_delta_metrics(df, timeframe_label):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0
    
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp'], errors='coerce').dt.tz_localize(None)
    
    tz = pytz.timezone('US/Central')
    now = datetime.now(tz).replace(tzinfo=None)
    
    # Define mapping for delta windows
    # Format: timedelta(current_window_duration)
    mapping = {
        "1 hr": timedelta(hours=1),
        "12 hr": timedelta(hours=12),
        "24 hr": timedelta(days=1),
        "1 week": timedelta(weeks=1),
        "1 month": timedelta(days=30),
        "6 month": timedelta(days=182),
        "1 year": timedelta(days=365),
        "All Time": None
    }
    
    delta_duration = mapping.get(timeframe_label)
    
    if timeframe_label == "All Time":
        return len(temp_df), 0  # No delta for all time
    
    current_threshold = now - delta_duration
    previous_threshold = now - (delta_duration * 2)
    
    current_leads = len(temp_df[temp_df['Timestamp'] > current_threshold])
    previous_leads = len(temp_df[(temp_df['Timestamp'] > previous_threshold) & (temp_df['Timestamp'] <= current_threshold)])
    
    return current_leads, (current_leads - previous_leads)

# Main Dashboard
try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    
    # --- Sidebar for Timeframe Selection ---
    with st.sidebar:
        st.title("⚙️ Settings")
        timeframe = st.selectbox(
            "Performance Period:",
            ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "6 month", "1 year", "All Time"],
            index=2 # Defaults to 24 hr
        )
        st.markdown("---")
        st.markdown(f"**Last Sync:** {last_sync} CST")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    st.title("📋 Executive Oversight")

    # Metrics Section with Dynamic Timeframe
    p_count, p_delta = get_delta_metrics(raw_prod_df, timeframe)
    r_count, r_delta = get_delta_metrics(raw_rec_df, timeframe)
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    with m_col2:
        st.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # Search & Filter
    st.markdown("### 🔍 Search & Filter")
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        search_query = st.text_input("Search by Full Name:", placeholder="Start typing...")
    with f_col2:
        selected_status = st.selectbox("Filter by Status:", ["All", "New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"])

    def process_display_df(df):
        if df.empty: return df
        filtered = df.copy()
        
        if search_query and 'Full Name' in filtered.columns:
            filtered = filtered[filtered['Full Name'].str.contains(search_query, case=False, na=False)]
        
        if selected_status != "All" and 'Status' in filtered.columns:
            filtered = filtered[filtered['Status'] == selected_status]
        
        # Action columns
        if 'Email Address' in filtered.columns:
            filtered['📧'] = filtered['Email Address'].apply(lambda x: f"mailto:{x}" if x else "")
        if 'Phone Number' in filtered.columns:
            filtered['📞'] = filtered['Phone Number'].apply(lambda x: f"tel:{x}" if x else "")
            
        # Reorder columns
        cols = list(filtered.columns)
        base_cols = [c for c in cols if c not in ['📧', '📞']]
        if 'Email Address' in base_cols:
            base_cols.insert(base_cols.index('Email Address') + 1, '📧')
        if 'Phone Number' in base_cols:
            base_cols.insert(base_cols.index('Phone Number') + 1, '📞')
            
        return filtered[base_cols]

    display_prod = process_display_df(raw_prod_df)
    display_rec = process_display_df(raw_rec_df)

    # Table Config
    column_configuration = {
        "Email Address": st.column_config.TextColumn("Email Address"),
        "📧": st.column_config.LinkColumn(" ", display_text="Email Lead"),
        "Phone Number": st.column_config.TextColumn("Phone Number"),
        "📞": st.column_config.LinkColumn(" ", display_text="Call Lead"),
    }

    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])
    with tab1:
        if not display_prod.empty:
            st.dataframe(display_prod.rename(index=lambda x: x + 1), use_container_width=True, column_config=column_configuration)
    with tab2:
        if not display_rec.empty:
            st.dataframe(display_rec.rename(index=lambda x: x + 1), use_container_width=True, column_config=column_configuration)

    # CRM Update Section
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
            match = df_to_use[df_to_use['Email Address'] == lead_email]
            if not match.empty:
                lead_data = match.iloc[0]
                col_s, col_n = st.columns(2)
                with col_s:
                    status_options = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
                    new_status = st.selectbox("New Status:", status_options, index=status_options.index(lead_data.get('Status', 'New')) if lead_data.get('Status') in status_options else 0)
                with col_n:
                    new_note = st.text_area("New Notes:", value=str(lead_data.get('Notes', '')))
                if st.button("Save Changes to Google Sheet"):
                    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
                    ws = gc.open("Lead Manager").worksheet(target)
                    cell = ws.find(lead_email)
                    clean_header = [h.strip() for h in ws.row_values(1)]
                    ws.update_cell(cell.row, clean_header.index("Status") + 1, new_status)
                    ws.update_cell(cell.row, clean_header.index("Notes") + 1, new_note)
                    st.success("Updated!")
                    st.cache_data.clear()
                    st.rerun()

    with st.sidebar:
        st.markdown("---")
        st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
        st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")

except Exception as e:
    st.error(f"Error: {e}")
