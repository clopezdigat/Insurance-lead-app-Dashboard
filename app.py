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
        
        # Clean headers
        prod_df.columns = [c.strip() for c in prod_df.columns]
        rec_df.columns = [c.strip() for c in rec_df.columns]
        
        tz = pytz.timezone('US/Central')
        sync_time = datetime.now(tz).strftime("%I:%M %p")
        return prod_df, rec_df, sync_time
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Error"

# Main Dashboard
try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    st.title("📋 Executive Oversight")

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
        
        # --- THE FIX: Create separate link columns ---
        # The main columns stay 100% CLEAN.
        if 'Email Address' in filtered.columns:
            filtered['📧'] = filtered['Email Address'].apply(lambda x: f"mailto:{x}" if x else "")
        if 'Phone Number' in filtered.columns:
            filtered['📞'] = filtered['Phone Number'].apply(lambda x: f"tel:{x}" if x else "")
        
        return filtered

    display_prod = process_display_df(raw_prod_df)
    display_rec = process_display_df(raw_rec_df)

    # Table Configuration
    # We show the raw data as TEXT (Clean) and the icons as LINKS (Functional)
    column_configuration = {
        "Email Address": st.column_config.TextColumn("Email Address"),
        "Phone Number": st.column_config.TextColumn("Phone Number"),
        "📧": st.column_config.LinkColumn("📧", display_text="Send Email"),
        "📞": st.column_config.LinkColumn("📞", display_text="Call"),
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
        st.markdown(f"**Last Sync:** {last_sync} CST")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
        st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")

except Exception as e:
    st.error(f"Error: {e}")
