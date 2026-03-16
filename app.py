import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
import pytz
import plotly.express as px

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

def get_delta_metrics(df, timeframe_label):
    if df.empty or 'Timestamp' not in df.columns:
        return 0, 0, df
    
    temp_df = df.copy()
    temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp'], errors='coerce').dt.tz_localize(None)
    
    tz = pytz.timezone('US/Central')
    now = datetime.now(tz).replace(tzinfo=None)
    
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
        return len(temp_df), 0, temp_df
    
    current_threshold = now - delta_duration
    previous_threshold = now - (delta_duration * 2)
    
    current_df = temp_df[temp_df['Timestamp'] > current_threshold]
    previous_leads = len(temp_df[(temp_df['Timestamp'] > previous_threshold) & (temp_df['Timestamp'] <= current_threshold)])
    
    return len(current_df), (len(current_df) - previous_leads), current_df

# Main Dashboard
try:
    raw_prod_df, raw_rec_df, last_sync = get_data()
    
    with st.sidebar:
        st.title("⚙️ Settings")
        timeframe = st.selectbox(
            "Performance Period:",
            ["1 hr", "12 hr", "24 hr", "1 week", "1 month", "6 month", "1 year", "All Time"],
            index=2
        )
        st.markdown("---")
        st.markdown(f"**Last Sync:** {last_sync} CST")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    st.title("📋 Executive Oversight")

    # Get Dynamic Data for Charts
    p_count, p_delta, filtered_prod = get_delta_metrics(raw_prod_df, timeframe)
    r_count, r_delta, filtered_rec = get_delta_metrics(raw_rec_df, timeframe)
    
    # 1. METRICS
    m_col1, m_col2 = st.columns(2)
    m_col1.metric(f"Product Leads ({timeframe})", p_count, delta=int(p_delta) if timeframe != "All Time" else None)
    m_col2.metric(f"Recruits ({timeframe})", r_count, delta=int(r_delta) if timeframe != "All Time" else None)

    # 2. VISUAL ANALYTICS
    st.markdown("### 📈 Visual Analytics")
    v_col1, v_col2, v_col3 = st.columns(3)

    with v_col1:
        st.write("**Lead Volume Trend**")
        combined_df = pd.concat([
            filtered_prod.assign(Type='Product'), 
            filtered_rec.assign(Type='Recruit')
        ])
        if not combined_df.empty and 'Timestamp' in combined_df.columns:
            trend_data = combined_df.set_index('Timestamp').resample('D').size().reset_index(name='Leads')
            fig_trend = px.line(trend_data, x='Timestamp', y='Leads', color_discrete_sequence=['#3b0710'])
            fig_trend.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.caption("Not enough data for trend.")

    with v_col2:
        st.write("**Location Distribution**")
        loc_col = 'State' if 'State' in filtered_prod.columns else 'City'
        if not filtered_prod.empty and loc_col in filtered_prod.columns:
            loc_data = filtered_prod[loc_col].value_counts().reset_index()
            fig_loc = px.pie(loc_data, values='count', names=loc_col, color_discrete_sequence=['#3b0710', '#D4AF37', '#7a111a'])
            fig_loc.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_loc, use_container_width=True)
        else:
            st.caption("No location data found.")

    with v_col3:
        st.write("**Interest Breakdown**")
        interest_col = 'Product Interest' if 'Product Interest' in filtered_prod.columns else 'Interest'
        if not filtered_prod.empty and interest_col in filtered_prod.columns:
            int_data = filtered_prod[interest_col].value_counts().reset_index()
            fig_int = px.bar(int_data, x=interest_col, y='count', color_discrete_sequence=['#D4AF37'])
            fig_int.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_int, use_container_width=True)
        else:
            st.caption("No interest data found.")

    # 3. SEARCH & TABLE
    st.markdown("---")
    st.markdown("### 🔍 Search & Filter")
    f_col1, f_col2 = st.columns(2)
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
        
        # Link Logic
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

    column_configuration = {
        "Email Address": st.column_config.TextColumn("Email Address"),
        "📧": st.column_config.LinkColumn(" ", display_text="Email"),
        "Phone Number": st.column_config.TextColumn("Phone Number"),
        "📞": st.column_config.LinkColumn(" ", display_text="Call"),
    }

    tab1, tab2 = st.tabs(["🛍️ Product Leads", "🤝 Recruitment Leads"])
    with tab1:
        st.dataframe(display_prod.rename(index=lambda x: x + 1), use_container_width=True, column_config=column_configuration)
    with tab2:
        st.dataframe(display_rec.rename(index=lambda x: x + 1), use_container_width=True, column_config=column_configuration)

    # 4. UPDATE SECTION
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
            if st.button("Save Changes"):
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
        st.write("[Client Portal](...)")
        st.write("[Recruitment Portal](...)")

except Exception as e:
    st.error(f"Error: {e}")
