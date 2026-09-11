import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io
import psycopg2
from supabase import create_client, Client
import re

# ==========================================================
# 1. PAGE CONFIGURATION
# ==========================================================
st.set_page_config(page_title="Smart Dashboard Pro", layout="wide")

# ==========================================================
# 2. SUPABASE AUTH CONFIGURATION (HARDCODED - NO ENV FILE)
# ==========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"] 

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Multi-stage Application Navigation Engine Tracking State
if "app_stage" not in st.session_state:
    st.session_state.app_stage = "landing" # Options: landing, demo, auth, dashboard
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ==========================================================
# 3. DATABASE CONFIGURATION
# ==========================================================
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="://supabase.com",  
            user="postgres.qurlcswocgjcuvhdcbze",
            password="Digchhen2001@",
            port=5432,
            database="postgres"
        )
        return conn
    except Exception as db_error:
        st.error(f"Supabase Connection Error: {db_error}")
        return None

# ==========================================================
# REUSABLE CORE INTERFACE DATA PARSING ENGINE
# ==========================================================
def render_core_dashboard(df, is_demo_mode=False):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗺️ Column Mapping Settings")
    
    adjust_manually = st.sidebar.checkbox("🔧 Adjust Columns Manually", value=True)
    columns_list = list(df.columns)
    
    rev_keywords = ['revenue', 'total', 'subtotal', 'gross sales', 'net sales', 'sales', 'amount', 'price', 'income', 'turnover', 'rev','cash_inflow']
    ad_keywords = ['spend', 'ad spend', 'amount spent', 'cost', 'google cost', 'meta spend', 'facebook spend', 'clicks cost', 'ad_spend', 'ad','promo_budget']
    cost_keywords = ['cogs', 'cost of goods', 'supplier cost', 'shipping cost', 'expenses', 'other costs', 'fees', 'othercost', 'other_cost', 'cost', 'other', 'fixed_fees']
    
    # Extract defaults using robust fallback mechanisms
    def_rev = next((c for c in columns_list if any(k in str(c).lower() for k in rev_keywords)), columns_list[0])
    def_ad = next((c for c in columns_list if any(k in str(c).lower() for k in ad_keywords)), columns_list[0])
    
    # Ensure cost default matching arrays filter smoothly without throwing list index mismatches
    def_costs = [c for c in columns_list if any(k.lower() in str(c).lower() for k in cost_keywords)]

    if adjust_manually:
        rev_col = st.sidebar.selectbox("Select Revenue Column:", columns_list, index=columns_list.index(def_rev))
        ad_col = st.sidebar.selectbox("Select Ad Spend Column:", columns_list, index=columns_list.index(def_ad))
        cost_cols = st.sidebar.multiselect("Select Other Costs Columns:", columns_list, default=def_costs)
    else:
        rev_col, ad_col, cost_cols = def_rev, def_ad, def_costs

    def clean_to_numeric_series(series):
        def parse_value(val):
            val_str = str(val).strip().replace('$', '').replace('₹', '').replace(',', '')
            if val_str == '' or val_str == '-':
                return 0.0
            if val_str.startswith('(') and val_str.endswith(')'):
                val_str = '-' + val_str[1:-1]
            try:
                return float(val_str)
            except ValueError:
                return 0.0
        numeric_series = series.apply(parse_value)
        return numeric_series.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    def extract_discount_value(val, row_revenue=0.0):
        if pd.isna(val):
            return 0.0
        val_str = str(val).strip()
        is_percentage = '%' in val_str
        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
        if numbers:
            extracted_num = abs(float(numbers[0]))
            if is_percentage:
                return (extracted_num / 100.0) * row_revenue
            else:
                return extracted_num
        val_lower = val_str.lower()
        if "bogo" in val_lower:
            return 15.00  
        elif "free shipping" in val_lower:
            return 5.00   
        return 0.0

    df['clean_rev_series'] = clean_to_numeric_series(df[rev_col])
    df['clean_ad_series'] = clean_to_numeric_series(df[ad_col])

    total_rev = np.sum(df['clean_rev_series'].to_numpy())
    total_ad = np.sum(df['clean_ad_series'].to_numpy())

    total_cost_series = pd.Series(0.0, index=df.index)
    for col in cost_cols:
        total_cost_series += clean_to_numeric_series(df[col])
    total_costs = np.sum(total_cost_series.to_numpy())

    discount_col = None
    for col_name in df.columns:
        if str(col_name).strip().lower() in ['discount', 'discounts']:
            discount_col = col_name
            break  

    if discount_col and discount_col in df.columns:
        clean_discount_series = df.apply(
            lambda row: extract_discount_value(row[discount_col], row['clean_rev_series']), 
            axis=1
        )
        total_discounts = np.sum(clean_discount_series.to_numpy())
    else:
        total_discounts = 0.0

    net_rev = total_rev - total_discounts
    net_profit = net_rev - (total_ad + total_costs)
    margin = (net_profit / net_rev) * 100.0 if net_rev != 0.0 else 0.0
    roas = total_rev / total_ad if total_ad > 0.0 else 0.0
    
    st.sidebar.success("✅ All Auto-Mapped Columns Processed and Calculated Successfully!")

    st.write("📊 **Dashboard Data Preview (Processed Values):**")
    st.write(df.head(3)) 

    st.markdown("---")
    st.subheader("🔑 Key Metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Net Profit", f"${net_profit:,.2f}")
    c2.metric("Profit Margin", f"{margin:.2f}%")
    c3.metric("ROAS", f"{roas:.2f}x")

    st.markdown("---")
    st.subheader("📊 Expense vs Revenue Breakdown")

    financial_data = {
        'Category': ['Net Profit', 'Ad Spend', 'Other Costs'],
        'Amount': [max(0.0, net_profit), total_ad, total_costs]
    }

    if sum(financial_data['Amount']) == 0:
        financial_data['Amount'] = [1.0, 0.0, 0.0]
        chart_title = "Revenue Distribution (No data processed)"
    else:
        chart_title = "Revenue & Expense Distribution"

    profit_color = '#2ec4b6' if net_profit >= 0 else '#e63946'

    fig = px.pie(
        financial_data, 
        values='Amount', 
        names='Category', 
        hole=0.65,  
        color='Category',
        color_discrete_map={
            'Other Costs': '#4361ee', 
            'Ad Spend': '#7209b7', 
            'Net Profit': profit_color
        }
    )

    fig.update_traces(
        textinfo='label+percent',
        textposition='outside', 
        textfont=dict(size=13, family="Arial"),
        pull=[0.05, 0, 0] 
    )

    formatted_profit = f"${net_profit:,.2f}" if net_profit >= 0 else f"-${abs(net_profit):,.2f}"

    fig.update_layout(
        showlegend=False,
        margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',  
        plot_bgcolor='rgba(0,0,0,0)',
        annotations=[
            dict(
                text=f"<span style='font-size:11px; color:#6c757d; font-weight:normal;'>NET PROFIT</span><br><b style='font-size:22px; color:{profit_color};'>{formatted_profit}</b>",
                x=0.5, y=0.5,
                showarrow=False,
                align="center"
            )
        ]
    )

    st.plotly_chart(fig, use_container_width=True)
    return net_profit, margin

# ==================================================================
# SIDEBAR TESTING UTILITIES FUNCTION
# ==================================================================
def render_testing_sidebar_tools():
    st.sidebar.markdown("### 🛠️ Testing Tools")
    
    # 🌟 FIXED: Fully populated arrays for the download tools, no syntax errors
    messy_df = pd.DataFrame({
        'Transaction_Date': pd.date_range(start='2026-08-01', periods=10),
        'Cash_Inflow':,
        'Promo_Budget':,
        'Fixed_Fees': [100, 120, 110, 130, 140, 150, 125, 160, 175, 165]
    })

    def make_buffer(dataframe):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            dataframe.to_excel(writer, index=False, sheet_name='Sheet1')
        return buf.getvalue()

    st.sidebar.download_button(
        label="📥 Download Clean Excel Data",
        data=make_buffer(messy_df),
        file_name="clean_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.sidebar.download_button(
        label="📥 Download Messy Excel Data",
        data=make_buffer(messy_df),
        file_name="messy_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ==========================================================
# MULTI-STAGE ROUTING ENGINE
# ==========================================================

# STAGE 1: HIGH-CONVERSION PUBLIC LANDING VIEW
if st.session_state.app_stage == "landing":
    st.title("🚀 Stop Guessing Your E-commerce Margins")
    st.subheader("Instantly calculate net profits from your store data logs without linking risky live API endpoints.")
    
    st.write(" ")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✨ View Live Sandbox Sandbox (No Sign Up Needed)", use_container_width=True, type="primary"):
