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
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    sh = gc.open("Lead Manager")
    
    prod_df = pd.DataFrame(sh.worksheet("Product").get_all_records())
    rec_df = pd.DataFrame(sh.worksheet("Recruitment").get_all_records())
    
    # Clean headers by stripping whitespace
    prod_df.columns = [c.strip() for c in prod_df.columns]
    rec_df.columns = [c.strip() for c in rec_df.columns]
    
    return prod_df, rec_df

# Helper Function for Metrics
def get_delta_metrics(df):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0
    
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp']).dt.tz_localize(None)
    
    tz = pytz.timezone('US/Central')
    now = datetime.now(tz).replace(tzinfo=None)
    
    yesterday = now - timedelta(days=1)
    day_before = now - timedelta(days=2)
    
    current_leads = len(temp_df[temp_df['Timestamp'] > yesterday])
    previous_leads = len(temp_df[(temp_df['Timestamp'] > day_before) & (temp_df['Timestamp'] <= yesterday)])
    
    return current_leads, (current_leads - previous_leads)

# Main Dashboard Logic
try:
    raw_prod_df, raw_rec_df = get_data()
    
    st.title("📋 Executive Oversight")

    # Search & filter bar
    st.markdown("### 🔍 Search & Filter")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        search_query = st.text_input("Search by Full Name:", placeholder="Start typing a name...")
    
    with f_col2:
        all_statuses = ["All", "New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
        selected_status = st.selectbox("Filter by Status:", all_statuses)

    # Apply Logic to Dataframes
    def apply_filters(df):
        filtered = df.copy()
        
        # Smart Search: Only run if 'Full Name' exists in this specific sheet
        if search_query and 'Full Name' in filtered.columns:
            filtered = filtered[filtered['Full Name'].str.contains(search_query, case=False, na=False)]
            
        if selected_status != "All" and 'Status' in filtered.columns:
            filtered = filtered[filtered['Status'] == selected_status]
            
        return filtered

    display_prod = apply_filters(raw_prod_df)
    display_rec = apply_filters(raw_rec_df)

    # Metrics (Total Agency Activity)
    p_count, p_delta = get_delta_metrics(raw_prod_df)
    r_count, r_delta = get_delta_metrics(raw_rec_df)

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("New Product Leads (24h Total)", p_count, delta=int(p_delta))
    m_col2.metric("New Recruits (24h Total)", r_count, delta=int(r_delta))

    # Display Tabs
    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])

    with tab1:
        st.dataframe(display_prod.rename(index=lambda x: x + 1), use_container_width=True)
    with tab2:
        st.dataframe(display_rec.rename(index=lambda x: x + 1), use_container_width=True)

    # 5. CRM MANAGEMENT SECTION
    st.markdown("---")
    st.subheader("📝 Update Lead Progress")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        target = st.radio("Target Sheet:", ["Product", "Recruitment"], horizontal=True)
        df_to_use = raw_prod_df if target == "Product" else raw_rec_df
        lead_email = st.selectbox("Select Lead by Email Address:", df_to_use['Email Address'].tolist())
    
    with c2:
        lead_data = df_to_use[df_to_use['Email Address'] == lead_email].iloc[0]
        
        col_s, col_n = st.columns(2)
        with col_s:
            status_options = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
            existing_status = lead_data.get('Status', 'New')
            current_status_idx = status_options.index(existing_status) if existing_status in status_options else 0
            new_status = st.selectbox("New Status:", status_options, index=current_status_idx)
            
        with col_n:
            existing_note = lead_data.get('Notes', '')
            new_note = st.text_area("New Notes:", value=str(existing_note))

    if st.button("Save Changes to Google Sheet"):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            sh = gc.open("Lead Manager")
            ws = sh.worksheet(target)
            
            cell = ws.find(lead_email)
            header = ws.row_values(1)
            
            status_idx = header.index("Status") + 1
            notes_idx = header.index("Notes") + 1
            
            ws.update_cell(cell.row, status_idx, new_status)
            ws.update_cell(cell.row, notes_idx, new_note)
            
            st.success(f"Updated {lead_email} successfully!")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Update failed: {e}")

except Exception as e:
    st.error(f"Error loading data: {e}")

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🔗 Digital Suite")
    st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
    st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
