import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import pytz

# Branding & UI
st.set_page_config(page_title="Agency Admin", page icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { border-top: 6px solid #D4AF37; }
    h1, h2 { color: #3b0710; }
    div[data-testid="stMetricValue"] { color: #3b0710; }
    </style>
""", unsafe_allow_html=True)

# Data Connection
def get_data():
  gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
  sh = gc.open("Lead Manager")

  # Pulling from both tabs
  prod_df = pd.DataFrame(sh.worksheet("Product").get_all_records())
  rec_df = pd.DataFrame(sh.worksheet("Recruitment").get_all_records())
  return prod_df, rec_df

# Dashboard Layout
st.title("📋 Executive Oversight")

# 24-Hour Delta Logic
now = datetime.now(pytz.timezone('US/Central'))
# Logic to filter DFs for last 24 hours
col1.metric("New Product Leads (24h)", "5", delta="+2")
col2.metric("New Recruits (24h)", "3", delta="-1")

tab1, tab2 = st.tabs(["🛍️ Product Lead", "🤝 Recruitment Leads"])

with tab1:
  st.dataframe(prod_df, use_container_width=True)
with tab2:
  st.datafram(rec_df, use_container_width=True)

with st.sidebar:
  st.markdown("### Digital Suite")
  st.write("[Client Portal](https://insurance-inquiry-xhf7vrf3otrgfvwiki65bm.streamlit.app/)")
  st.write("[Recruitment Portal](https://insurance-lead-recruitment-fpyfxsjlzqywfqh9639pzf.streamlit.app/)")
  
