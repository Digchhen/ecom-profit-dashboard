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
# This must remain at the absolute top execution line of Streamlit
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

# Tracks whether the user session is currently verified
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "app_stage" not in st.session_state:
    st.session_state.app_stage = "landing"
# ==========================================================
# 3. DATABASE CONFIGURATION (PARAMETERS FIX FOR SPECIAL CHARACTERS)
# ==========================================================
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="aws-0-ap-south-1.pooler.supabase.com",  # 👈 Make sure there is NO ":// " here
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
# 4. THE PROTECTED APP GATE
# ==========================================================
if st.session_state.logged_in:

    # 👤 Grab active user email
    current_user_email = supabase.auth.get_user().user.email
    st.sidebar.markdown(f"👤 Account: **{current_user_email}**")
    
    # 💳 MVP SUBSCRIPTION ANNOUNCEMENT GATE
    st.sidebar.markdown("---")
    st.sidebar.info("⏳ **Account Plan: Early-Bird Free Trial**")
    st.sidebar.write("This MVP is free during our beta testing period. Standard subscriptions will start at **$19/month** after launch.")
    
    # Mock Upgrade Button to capture intent
    if st.sidebar.button("✨ Upgrade to Premium (Coming Soon)", use_container_width=True):
        st.sidebar.balloons()
        st.sidebar.success("Thank you for your interest! We have logged your request and will notify you the moment premium plans go live.")
        
        # 📊 NEW TRACKER LOGIC: Insert row into cloud database table
        conn = get_db_connection()
        if conn:
            try:
                click_cursor = conn.cursor()
                click_cursor.execute("""
                    INSERT INTO upgrade_clicks (user_email)
                    VALUES (%s);
                """, (current_user_email,))
                conn.commit()
                click_cursor.close()
                conn.close()
                print("🎉 Click successfully committed to Postgres backend!")
            except Exception as click_err:
                print(f"Click tracking failed: {click_err}")
    
    # 🚪 Sidebar logout button keeps it clean out of the primary application viewport
    if st.sidebar.button("Log Out 🚪", type="primary"):
        supabase.auth.sign_out()
        st.session_state.logged_in = False
        st.rerun()

    # --- YOUR ORIGINAL APPLICATION STARTS HERE (INDENTED 4 SPACES) ---
    # 👇 ALL THIS CODE IS NOW INDENTED BY 4 SPACES 👇
    st.title("📊 E-Commerce Profit Dashboard")

    # Quietly auto-initialize user & upload history logs tables in the cloud background
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Table A: Basic users log infrastructure
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Table B: Real-time file upload tracking history logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upload_logs (
                id SERIAL PRIMARY KEY,
                file_name VARCHAR(255) NOT NULL,
                net_profit NUMERIC,
                profit_margin NUMERIC,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # 📊 Table C: Log every time someone requests to upgrade to premium 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upgrade_clicks (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()

    # ==========================================================
    # 3. SIDEBAR TESTING TOOLS
    # ==========================================================
    st.sidebar.markdown("### 🛠️ Testing Tools")

    # Fixed mock arrays for downloading
    messy_df = pd.DataFrame({
        'Transaction_Date': pd.date_range(start='2026-08-01', periods=10),
        'Cash_Inflow': [10000, 12000, 11000, 15000, 13000, 16000, 14000, 17000, 18000, 16500],
        'Promo_Budget': [3000, 3500, 3200, 4000, 3800, 4200, 3900, 4500, 4800, 4300],
        'Fixed_Fees': [2000, 2200, 1800, 2500, 2100, 2800, 1900, 2300, 2400, 2200]
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
    # 4. MAIN INTERFACE & FILE UPLOADER
    # ==========================================================
    st.markdown("### 📂 Upload Your Data Spreadsheet")
    uploaded_file = st.file_uploader("Upload your data spreadsheet", type=["csv", "xlsx"], label_visibility="collapsed")

    if uploaded_file is None:
        st.info("ℹ️ Please upload a spreadsheet to see the dashboard metrics.")
    else:
        try:
            # Load File
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                    
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🗺️ Column Mapping Settings")
            
            adjust_manually = st.sidebar.checkbox("🔧 Adjust Columns Manually", value=True)
            columns_list = ["None"] + list(df.columns)
            
            rev_keywords = ['revenue', 'total', 'subtotal', 'gross sales', 'net sales', 'sales', 'amount', 'income', 'turnover', 'rev','cash_inflow','net revenue','gross revenue calculated','net sales']
            ad_keywords = ['spend', 'ad spend', 'amount spent', 'cost', 'google cost', 'meta spend', 'facebook spend', 'clicks cost', 'ad_spend', 'ad','promo_budget']
            cost_keywords = ['cogs', 'cost of goods', 'supplier cost', 'shipping cost', 'expenses', 'other costs', 'fees', 'othercost', 'other_cost', 'cost','discount','discounts','other','fixed_fees']
            
            # Check exact matches first, then fallback to partial substring matching
            # --- 🗺️ CLEAN AUTOMATIC COLUMN MAPPING (Lines 188-205) ---
            def_rev = next((c for c in columns_list if str(c).lower().strip() in rev_keywords), None)
            if not def_rev:
                # Substring matching, skipping generic false-positives
                def_rev = next((c for c in columns_list if any(k in str(c).lower() for k in rev_keywords if k not in ['amount', 'price'])), None)
            if not def_rev:
                def_rev = "None"
    
            def_ad = next((c for c in columns_list if str(c).lower().strip() in ad_keywords), None)
            if not def_ad:
                # Substring matching, skipping generic 'cost'
                def_ad = next((c for c in columns_list if any(k in str(c).lower() for k in ad_keywords if k != 'cost')), None)
            if not def_ad:
                def_ad = "None"
    
            # --- 🗺️ ROBUST MULTI-COLUMN MATCHING FOR OTHER COSTS ---
            def_costs = []
    
            # Check for explicit exact keyword matches first
            exact_matches = [c for c in columns_list if str(c).lower().strip() in cost_keywords]
            def_costs.extend(exact_matches)
    
            # Add any fallback column names containing BOTH 'total' and 'cost'
            total_cost_matches = [c for c in columns_list if 'total' in str(c).lower() and 'cost' in str(c).lower()]
            for c in total_cost_matches:
                if c not in def_costs:
                    def_costs.append(c)
    
            # Scan and auto-grab discount columns if present in the spreadsheet
            discount_keywords = ['discount', 'markdown', 'coupon', 'deduction', 'rebate']
            discount_matches = [c for c in columns_list if any(dk in str(c).lower() for dk in discount_keywords)]
            for c in discount_matches:
                if c not in def_costs:
                    def_costs.append(c)
    
            # Final Substring fallback from standard cost_keywords if list remains empty
            if not def_costs:
                substring_matches = [c for c in columns_list if any(k in str(c).lower() for k in cost_keywords)]
                if substring_matches:
                    def_costs = [substring_matches[0]]
    
            # Fallback safety baseline structure
            if not def_costs:
                def_costs = ["None"]
            
            if adjust_manually:
                # 1. Smart keyword finder for the date field right inside the dropdown index
                def_date = next((c for c in columns_list if any(k in str(c).lower() for k in ['date', 'time', 'timestamp', 'day'])), columns_list[0] if columns_list else None)
                
                date_col = st.sidebar.selectbox(
                    "Select Date Column:", 
                    columns_list, 
                    index=columns_list.index(def_date) if def_date in columns_list else 0
                )
                rev_col = st.sidebar.selectbox("Select Revenue Column:", columns_list, index=columns_list.index(def_rev))
                ad_col = st.sidebar.selectbox("Select Ad Spend Column:", columns_list, index=columns_list.index(def_ad))
                cost_cols = st.sidebar.multiselect("Select other costs columns:", columns_list, default=def_costs)
            else:
                # 2. Automated path: auto-detects the date column if manual toggle is off
                def_date = next((c for c in columns_list if any(k in str(c).lower() for k in ['date', 'time', 'timestamp', 'day'])), None)
                
                date_col = def_date
                rev_col, ad_col, cost_cols = def_rev, def_ad, def_costs

            # --- ADD THIS LOGIC HERE (Around Line 251, before your cleaning function) ---

            # Flag to tell your downstream dashboard whether time-charts should be rendered
            has_date_data = True
                
            if date_col == "None":
                    has_date_data = False
                    # Do not let your script convert or verify "None" against your dataframe columns!
            
            def clean_to_numeric_series(series):
                """
                Cleans financial text columns. Preserves negative values, 
                converts invalid text to 0.0, and standardizes formats.
                """
                def parse_value(val):
                    # Force to string, clean spaces, and remove commas/currency symbols
                    val_str = str(val).strip().replace('$', '').replace('₹', '').replace(',', '')
                    
                    if val_str == '' or val_str == '-':
                        return 0.0
                        
                    # Convert accounting brackets (100.00) into standard negative -100.00
                    if val_str.startswith('(') and val_str.endswith(')'):
                        val_str = '-' + val_str[1:-1]
                        
                    try:
                        # Safely cast to float
                        return float(val_str)
                    except ValueError:
                        # If the cell contains random words or unparseable alphabets, default to 0.0
                        return 0.0
        
                # Apply the safe row-by-row parser
                numeric_series = series.apply(parse_value)
                
                # Clean out extreme infinity cases if any exist
                return numeric_series.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        
        
            # ==========================================
            # 2. ADVANCED SMART EXTRACTION FOR DISCOUNTS
            # ==========================================
            def extract_discount_value(val, row_revenue=0.0):
                """
                Cleans and extracts the actual discount dollar value from various formats
                based on the following rules:
                - 0.14 -> 14% discount
                - 14%  -> 14% discount
                - 14   -> 14% discount
                - $14  -> $14.00 flat cash
                """
            
                # Safely handle blank or missing cells
                if pd.isna(val):
                    return 0.0
            
                # 1. Analyze the string format for flags
                val_str = str(val).strip()
                is_percentage = '%' in val_str
                is_dollar = '$' in val_str or 'USD' in val_str.upper()
            
                # 2. Extract digits out of the text (e.g., "$14.00" -> 14.0)
                numbers = re.findall(r'[-+]?\d*\.\d+|\d+', val_str)
                if not numbers:
                    return 0.0
                extracted_num = abs(float(numbers[0]))
            
                # 3. Apply your precise logic conditions
                if is_dollar:
                    # Rule: $14 -> Flat $14.00 cash
                    return extracted_num
                    
                elif is_percentage:
                    # Rule: 14% -> 14% discount rate
                    return (extracted_num / 100.0) * row_revenue
                    
                elif 0.0 < extracted_num < 1.0:
                    # Rule: 0.14 -> 14% discount rate
                    return extracted_num * row_revenue
                    
                elif extracted_num >= 1.0:
                    # Rule: 14 (Plain number) -> 14% discount rate
                    return (extracted_num / 100.0) * row_revenue
                    
                else:
                    return 0.0
        
                # Fallback strategic keyword rules for pure text strings
                val_lower = val_str.lower()
                if "bogo" in val_lower:
                    return 15.00  # Default flat savings value for standard BOGO tags
                elif "free shipping" in val_lower:
                    return 5.00   # Average absorbed shipping perk value
                    
                return 0.0
        
        
            # ==========================================
            # 3. EXECUTING THE ORDER OF OPERATIONS MATH
            # ==========================================
            # --- STEP A: Standard Clean for core metrics ---
    
            # 1. Clean Revenue Column Safely (Creates a 0.0 series if None)
            if rev_col == "None" or not rev_col:
                df['clean_rev_series'] = pd.Series(0.0, index=df.index)
            else:
                df['clean_rev_series'] = clean_to_numeric_series(df[rev_col])
                
            # 2. Clean Ad Spend Column Safely (Creates a 0.0 series if None)
            if ad_col == "None" or not ad_col:
                df['clean_ad_series'] = pd.Series(0.0, index=df.index)
            else:
                df['clean_ad_series'] = clean_to_numeric_series(df[ad_col])
        
            # Calculate individual total numbers using your original np.sum logic
            total_rev = np.sum(df['clean_rev_series'].to_numpy())
            total_ad = np.sum(df['clean_ad_series'].to_numpy())
        
            # 3. Sum up all individual cost columns safely (skips "None")
            total_cost_series = pd.Series(0.0, index=df.index)
            if 'cost_cols' in locals() and cost_cols:
                for col in cost_cols:
                    if col != "None" and col in df.columns:
                        total_cost_series += clean_to_numeric_series(df[col])
                        
            # Calculate total costs from the series
            total_costs = np.sum(total_cost_series.to_numpy())

        
        
            # --- STEP B: Smart Auto-Fuzzy Match for Discount Columns ---
            discount_col = None
            
            # Intelligently scan all columns for variations like 'discount', 'Discount', 'discounts', etc.
            for col_name in df.columns:
                if str(col_name).strip().lower() in ['discount', 'discounts']:
                    discount_col = col_name
                    break  # Found the matching structural column name, break loop
        
            # Also define alternative common spelling names to prevent validation crash checks later
            discount_column = discount_col 
        
            if discount_col and discount_col in df.columns:
                # Pass BOTH the discount string and row revenue to handle variations & percentages perfectly
                clean_discount_series = df.apply(
                    lambda row: extract_discount_value(row[discount_col], row['clean_rev_series']), 
                    axis=1
                )
                total_discounts = np.sum(clean_discount_series.to_numpy())
            else:
                total_discounts = 0.0
        
        
            # --- STEP C: Final Math Operations ---
            # 1. Net Revenue: Gross Revenue minus markdowns
            net_rev = total_rev - total_discounts
        
            # 2. Net Profit: Out-of-pocket revenue minus total advertising spend and operating costs
            net_profit = net_rev - (total_ad + total_costs)
        
            # 3. Profit Margin: Fixed to show negative percentages if you take a loss (safe division check)
            margin = (net_profit / net_rev) * 100.0 if net_rev != 0.0 else 0.0
        
            # 4. ROAS: Fixed to standard marketing standard (Gross Revenue / Ad Spend)
            roas = total_rev / total_ad if total_ad > 0.0 else 0.0
            
            st.sidebar.success("✅ All Auto-Mapped Columns Processed and Calculated Successfully!")

            st.write("📊 **Uploaded Data Preview (Raw Values):**")
            st.write(df.head(3)) 

            st.markdown("---")
            st.subheader("🔑 Key Metrics")
            c1, c2, c3 = st.columns(3)
            c1.metric("Net Profit", f"${net_profit:,.2f}")
            c2.metric("Profit Margin", f"{margin:.2f}%")
            c3.metric("ROAS", f"{roas:.2f}x")

            conn = get_db_connection()
            if conn:
                try:
                    db_cursor = conn.cursor()
                    db_cursor.execute("""
                        INSERT INTO upload_logs (file_name, net_profit, profit_margin)
                        VALUES (%s, %s, %s);
                    """, (uploaded_file.name, float(net_profit), float(margin)))
                    conn.commit()
                    db_cursor.close()
                    conn.close()
                    st.success("Successfully logged real financial data metrics to Supabase!")
                except Exception as db_err:
                    st.warning(f"Could not log file to historical database: {db_err}")
                    
            st.markdown("---")
            st.subheader("📊 Expense vs Revenue Breakdown")
        
            financial_data = {
                'Category': ['Net Profit', 'Ad Spend', 'Other Costs'],
                'Amount': [max(0.0, net_profit), total_ad, total_costs]
            }
        
            if sum(financial_data['Amount']) == 0:
                financial_data['Amount'] = [1.0, 0.0, 0.0]
                chart_title = "Revenue & Expense Distribution (Please select numeric columns in sidebar)"
            else:
                chart_title = "Revenue & Expense Distribution"
        
            # Define color scheme dynamically: Teal if profitable, Red if losing money
            profit_color = '#2ec4b6' if net_profit >= 0 else '#e63946'
        
            # Build the updated Donut Chart
            import plotly.express as px
            fig = px.pie(
                financial_data, 
                values='Amount', 
                names='Category', 
                hole=0.65,  # Makes the hole wider to fit text nicely
                color='Category',
                color_discrete_map={
                    'Other Costs': '#4361ee', 
                    'Ad Spend': '#7209b7', 
                    'Net Profit': profit_color
                }
            )
        
            # Move text to the outside and make it bold
            fig.update_traces(
                textinfo='label+percent',
                textposition='outside', 
                textfont=dict(size=13, family="Arial"),
                pull=[0.05, 0, 0] # Gently highlights Net Profit
            )
        
            # Format the central text string elegantly
            formatted_profit = f"${net_profit:,.2f}" if net_profit >= 0 else f"-${abs(net_profit):,.2f}"
        
            # Place the center KPI callout metric
            fig.update_layout(
                showlegend=False,
                margin=dict(t=50, b=20, l=20, r=20),
                annotations=[
                    dict(
                        text=f"<span style='font-size:11px; color:#6c757d; font-weight:normal;'>NET PROFIT</span><br><b style='font-size:22px; color:{profit_color};'>{formatted_profit}</b>",
                        x=0.5, y=0.5,
                        showarrow=False,
                        align="center"
                    )
                ]
            )
            st.plotly_chart(fig, use_container_width=True, key="main_ecom_donut_chart")
           
            # --- PULL IN DATA FOR THE LINE CHART ---
            st.markdown("---")
            st.subheader("📈 Financial Performance Over Time")
            
            # 1. Add time grain control widget
            time_grain = st.radio(
                "View Scale:", 
                options=["Daily", "Weekly", "Monthly"], 
                horizontal=True
            )
            
            # 2. Check if a date column is selected in your sidebar configurations
            # Note: Ensure you define `date_col` in your sidebar selectboxes at the top of your file
            # 2. Render chart if date_col is captured from your sidebar selection
            if 'date_col' in locals() or 'date_col' in globals():
                if date_col and date_col != "None":
                    # Safely parse dates from data frame upload
                    chart_df = df[[date_col]].copy()
                    chart_df[date_col] = pd.to_datetime(chart_df[date_col])
                    
                    # Map values dynamically using your existing sidebar variables
                    chart_df['Revenue'] = df[rev_col]
                    chart_df['Total Expenses'] = df[ad_col] + df[cost_cols].sum(axis=1) if isinstance(cost_cols, list) and cost_cols else df[ad_col]
                    chart_df['Net Profit'] = chart_df['Revenue'] - chart_df['Total Expenses']
                            
                    # 3. Calculate the true date range spanned by the uploaded file
                    date_range_days = (chart_df[date_col].max() - chart_df[date_col].min()).days + 1
                    
                    # Smart time-grain fallback routing to prevent crashes
                    if time_grain == "Weekly" and date_range_days >= 7:
                        timeline = chart_df.resample('W', on=date_col).sum()
                    elif time_grain == "Monthly" and date_range_days >= 28:
                        timeline = chart_df.resample('ME', on=date_col).sum()
                    else:
                        # Fallback safely to standard date grouping if data is too short
                        if time_grain in ["Weekly", "Monthly"]:
                            st.info(f"💡 Info: Uploaded data spans only {date_range_days} days. Showing default daily breakdown.")
                        timeline = chart_df.groupby(date_col).sum()
                        
                    timeline = timeline.reset_index()
                    
                    # 4. Restructure columns into narrow format for multi-line display
                    melted_df = pd.melt(
                        timeline, 
                        id_vars=[date_col], 
                        value_vars=['Revenue', 'Total Expenses', 'Net Profit'],
                        var_name='Metric', 
                        value_name='Amount ($)'
                    )
                    
                    # 5. Build full Plotly line visualization
                    line_fig = px.line(
                        melted_df, 
                        x=date_col, 
                        y='Amount ($)', 
                        color='Metric',
                        color_discrete_map={
                            'Revenue': '#2ecc71',        # Balanced Green
                            'Total Expenses': '#e74c3c', # Balanced Red
                            'Net Profit': profit_color    # Connects with your custom center profit indicator!
                        },
                        template="plotly_dark"
                    )
                    
                    line_fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                    st.plotly_chart(line_fig, use_container_width=True, key="dashboard_line_timeline_chart")
                    
                # --- Upcoming Integrations Section ---
                st.write("---") 
                st.subheader("🔌 Upcoming Integrations")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Shopify Connect (Coming Soon)**")
                    st.caption("Sync live inventory tracking, automated ad platform spend metrics, and true multi-channel net profit.")
                    
                with col2:
                    feedback = st.feedback("thumbs", key="unique_real_shopify_vote")
                    
                if st.session_state.get("unique_real_shopify_vote") is not None:
                    is_positive = st.session_state.unique_real_shopify_vote == 0
                    
                    if is_positive:
                        st.success("Awesome! Glad to hear you're excited for Shopify automation.")
                        user_notes = st.text_input(
                            "What specific feature or metrics do you want us to support first?",
                            placeholder="e.g., TikTok Shop sync, Amazon Multi-channel...",
                            key="unique_real_shopify_positive_notes"
                        )
                        else:
                        st.info("Got it. Is there another platform integration you need instead?")
                        alt_notes = st.text_input(
                            "Tell us what integration would be more valuable to you:",
                            placeholder="e.g., WooCommerce, Stripe API, Custom CSV...",
                            key="unique_real_shopify_negative_notes"
                        )
                        
                        if st.button("Submit Alternative Choice", key="submit_shopify_alt_btn"):
                            if alt_notes.strip() != "":
                                try:
                                    supabase.table("user_feedback").insert({
                                        "vote_type": "thumbs_down",
                                        "user_suggestion": alt_notes                                    
                                    }).execute()
                                    
                                    st.toast("Thank you! We will look into building that integration.", icon="📣")
                                except Exception as e:
                                    st.error(f"Error: {e}")
                            else:
                                st.warning("⚠️ Please type your request before clicking submit!")
# ==========================================================
# 5. THE LOGIN SCREEN (FALLBACK ACCESS WITH SIGN-UP)
# ==========================================================
else:
    if st.session_state.app_stage == "landing":
        st.title("🚀 Stop Guessing Your E-commerce Margins")
        st.subheader("Instantly calculate net profits from your store data logs without linking risky live API endpoints.")
        st.write(" ")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✨ View Live Sandbox (No Sign Up Needed)", use_container_width=True, type="primary"):
                st.session_state.app_stage = "demo"
                st.rerun()
        with col2:
            if st.button("🔑 Account Member Access Portal / Upload CSV Direct", use_container_width=True):
                st.session_state.app_stage = "auth"
                st.rerun()

    elif st.session_state.app_stage == "demo":
        st.warning("⚡ Currently running in Sandbox Mode using sample row frameworks. Want to run calculations on your real store numbers?")
        if st.button("👉 Register Private Account & Open File Dropper", type="primary"):
            st.session_state.app_stage = "auth"
            st.rerun()
        st.divider()
        
       # 1. Generate Sandbox Dataset
        demo_df = pd.DataFrame({
            'Transaction_Date': pd.date_range(start='2026-09-01', periods=20),
            'revenue': [5000 + i*300 for i in range(20)],
            'spend': [1200 + i*80 for i in range(20)],
            'cogs': [800 + i*40 for i in range(20)]
        })
       # 1. Run the auto-calculation logic right before computing metrics

        # Define calculations helper 1
        def auto_calculate_gross_revenue(df):
            if 'Gross_Revenue_Calculated' not in df.columns:
                if 'revenue' in df.columns:
                    df['Gross_Revenue_Calculated'] = df['revenue']
                else:
                    df['Gross_Revenue_Calculated'] = 0
            return df

        # Define calculations helper 2
        def clean_to_numeric_series(series):
            """
            Cleans a pandas series by removing non-numeric characters (like $ or commas)
            and converting the data into numbers.
            """
            import pandas as pd
            cleaned = pd.to_numeric(series.astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            return cleaned.fillna(0)

        # 1. Run the auto-calculation logic right before computing metrics
        demo_df = auto_calculate_gross_revenue(demo_df)
                
        # 2. Compute Core Financial Metrics
        total_rev = float(demo_df['Gross_Revenue_Calculated'].sum())
        total_ad = float(demo_df['spend'].sum())
        total_costs = float(demo_df['cogs'].sum())
                
        net_profit = total_rev - total_ad - total_costs
        margin = (net_profit / total_rev) * 100.0 if total_rev != 0.0 else 0.0
        roas = total_rev / total_ad if total_ad > 0.0 else 0.0
                
        # 3. Clean and calculate the core sandbox series directly
        # Fix: Wrapped key names in proper quotes string formatting to match your sandbox columns
        demo_df['clean_rev_series'] = clean_to_numeric_series(demo_df['revenue'])
        demo_df['clean_ad_series'] = clean_to_numeric_series(demo_df['spend'])
                
        total_rev = float(np.sum(demo_df['clean_rev_series'].to_numpy()))
        total_ad = float(np.sum(demo_df['clean_ad_series'].to_numpy()))        
        
        # Sum up all sandbox preset cost columns directly
        total_cost_series = pd.Series(0.0, index=demo_df.index)
        if 'other_costs' in locals() and other_costs:
            for col in other_costs:
                if col in demo_df.columns:
                    total_cost_series += clean_to_numeric_series(demo_df[col])
                            
        total_costs = float(np.sum(total_cost_series.to_numpy()))        
                                             
            

        # --- FINAL MATH ---
        net_profit = total_rev - total_ad - total_costs
        margin = (net_profit / total_rev) * 100.0 if total_rev != 0.0 else 0.0
        roas = total_rev / total_ad if total_ad > 0.0 else 0.0


        
        # 3. Render Key Indicator Metrics Grid
        st.subheader("🔑 Key Metrics (Sandbox Data)")
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
        
        profit_color = '#2ec4b6' if net_profit >= 0 else '#e63946'
        
        # 4. Generate Interactive Donut Graph Layout
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
            textfont=dict(size=13, family="Arial")
        )
        
        fig.update_layout(
            showlegend=False,
            margin=dict(t=30, b=20, l=20, r=20),
            paper_bgcolor='rgba(0,0,0,0)',  
            plot_bgcolor='rgba(0,0,0,0)',
            annotations=[
                dict(
                    text=f"<span style='font-size:11px; color:#6c757d;'>NET PROFIT</span><br><b style='font-size:22px; color:{profit_color};'>${net_profit:,.2f}</b>",
                    x=0.5, y=0.5,
                    showarrow=False,
                    align="center"
                )
            ]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("")
        if st.button("⬅️ Back to Home"):
            st.session_state.app_stage = "landing"
            st.rerun()

    elif st.session_state.app_stage == "auth":
        col1, col2, col3 = st.columns(3)
        with col2:
                    st.write("")
                    st.markdown("<h2 style='text-align: center;'>🔐 Dashboard Portal</h2>", unsafe_allow_html=True)
                    
                    # Creates two clickable tabs for users
                    auth_tab, signup_tab = st.tabs(["🔒 Sign In", "📝 Create Account"])
                    
                    # --- TAB 1: LOG IN ---
                    with auth_tab:
                        st.write("Sign in with your credentials to unlock application metrics.")
                        with st.form("login_form"):
                            email = st.text_input("Email Address", placeholder="name@example.com")
                            password = st.text_input("Password", type="password", placeholder="••••••••")
                            submit = st.form_submit_button("Sign In", use_container_width=True)
            
                            if submit:
                                if email and password:
                                    try:
                                        response = supabase.auth.sign_in_with_password({
                                            "email": email.strip(),
                                            "password": password
                                        })
                                        st.session_state.logged_in = True
                                        st.success("Access Granted! Loading your dashboard...")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Authentication Failed: {e}")
                                else:
                                    st.warning("Please fill in both fields.")
            
                    # --- TAB 2: SELF-SERVICE SIGN UP ---
                    with signup_tab:
                        st.write("Create a new user account to access the system.")
                        with st.form("signup_form"):
                            new_email = st.text_input("New Email Address", placeholder="user@example.com")
                            new_password = st.text_input("Choose Password", type="password", placeholder="Minimum 6 characters")
                            signup_submit = st.form_submit_button("Register Account", use_container_width=True)
            
                            if signup_submit:
                                if new_email and new_password:
                                    if len(new_password) < 6:
                                        st.error("❌ Password must be at least 6 characters long.")
                                    else:
                                        try:
                                            # Registers the user directly into your Supabase database
                                            response = supabase.auth.sign_up({
                                                "email": new_email.strip(),
                                                "password": new_password
                                            })
                                            st.success("🎉 Account created successfully! You can now switch to the 'Sign In' tab and log in.")
                                        except Exception as e:
                                            st.error(f"Registration Failed: {e}")
                                else:
                                    st.warning("Please fill in both fields.")
                    st.write("")
                    if st.button("⬅️ Return to Landing Page", use_container_width=True):
                        st.session_state.app_stage = "landing"
                        st.rerun()       
        
