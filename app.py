import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz

# 1. Branding & UI
st.set_page_config(page_title="Agency Admin", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { border-top: 6px solid #D4AF37; }
    h1, h2 { color: #3b0710; }
    div[data-testid="stMetricValue"] { color: #3b0710; }
    </style>
""", unsafe_allow_html=True)

# 2. Data Connection
@st.cache_data(ttl=600)
def get_data():
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    sh = gc.open("Lead Manager")
    
    prod_df = pd.DataFrame(sh.worksheet("Product").get_all_records())
    rec_df = pd.DataFrame(sh.worksheet("Recruitment").get_all_records())
    return prod_df, rec_df

# 3. Helper Function for Metrics
def get_delta_metrics(df):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0
    
    # Process a copy to avoid modifying the displayed dataframe
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp']).dt.tz_localize(None)
    
    tz = pytz.timezone('US/Central')
    now = datetime.now(tz).replace(tzinfo=None)
    
    yesterday = now - timedelta(days=1)
    day_before = now - timedelta(days=2)
    
    current_leads = len(temp_df[temp_df['Timestamp'] > yesterday])
    previous_leads = len(temp_df[(temp_df['Timestamp'] > day_before) & (temp_df['Timestamp'] <= yesterday)])
    
    return current_leads, (current_leads - previous_leads)

# 4. Main Dashboard Logic
try:
    prod_df, rec_df = get_data()
    
    p_count, p_delta = get_delta_metrics(prod_df)
    r_count, r_delta = get_delta_metrics(rec_df)

    st.title("📋 Executive Oversight")

    col1, col2 = st.columns(2)
    col1.metric("New Product Leads (24h)", p_count, delta=int(p_delta))
    col2.metric("New Recruits (24h)", r_count, delta=int(r_delta))

    # Display Tabs
    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])

    with tab1:
        # Display with index starting at 1
        st.dataframe(prod_df.rename(index=lambda x: x + 1), use_container_width=True)
    with tab2:
        st.dataframe(rec_df.rename(index=lambda x: x + 1), use_container_width=True)

    # 5. CRM MANAGEMENT SECTION (Notes & Status)
    st.markdown("---")
    st.subheader("📝 Lead Management")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        target = st.radio("Target Sheet:", ["Product", "Recruitment"], horizontal=True)
        df_to_use = prod_df if target == "Product" else rec_df
        
        # Identify lead by Email Address (from your screenshot)
        lead_email = st.selectbox("Select Lead by Email Address:", df_to_use['Email Address'].tolist())
    
    with c2:
        # Get existing values
        lead_data = df_to_use[df_to_use['Email Address'] == lead_email].iloc[0]
        
        col_s, col_n = st.columns(2)
        with col_s:
            # Status Dropdown
            status_options = ["New", "Contacted", "Interested", "Follow-up Needed", "Enrolled", "Not Interested"]
            # Pre-select existing status if it exists, else "New"
            existing_status = lead_data.get('Status', 'New')
            current_status_idx = status_options.index(existing_status) if existing_status in status_options else 0
            
            new_status = st.selectbox("Update Status:", status_options, index=current_status_idx)
            
        with col_n:
            # Notes Area
            existing_note = lead_data.get('Notes', '')
            new_note = st.text_area("Update Notes:", value=str(existing_note))

    if st.button("Save Changes to Google Sheet"):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            sh = gc.open("Lead Manager")
            ws = sh.worksheet(target)
            
            # Find the row
            cell = ws.find(lead_email)
            header = ws.row_values(1)
            
            # Find column indices
            status_idx = header.index("Status") + 1
            notes_idx = header.index("Notes") + 1
            
            # Update values
            ws.update_cell(cell.row, status_idx, new_status)
            ws.update_cell(cell.row, notes_idx, new_note)
            
            st.success(f"Updated {lead_email} successfully!")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Update failed: {e}. Check if 'Status' and 'Notes' columns exist in your sheet.")

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
