import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Portfolio Allocation Calculator", page_icon="💰", layout="wide")

# --- Dashboard Redesign Styling ---
st.markdown("""
<style>
    /* Global Background & Variables */
    :root {
        --primary-accent: #FF8B76;
        --bg-mint: #EFF6F3;
        --sidebar-dark: #2D2D3A;
        --card-bg: #FFFFFF;
        --text-dark: #2D2D3A;
    }

    .stApp {
        background-color: var(--bg-mint);
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-dark);
    }
    
    /* Input Labels in Sidebar */
    [data-testid="stSidebar"] label p {
        color: white !important;
        font-weight: 500 !important;
    }
    
    /* Selectbox/Input values in sidebar */
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
        color: var(--text-dark) !important;
    }

    /* Expander Styling in Sidebar */
    [data-testid="stSidebar"] details {
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        background-color: rgba(255,255,255,0.03) !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }
    
    [data-testid="stSidebar"] details summary {
        background-color: transparent !important;
        color: white !important;
        padding: 5px 10px !important;
    }
    
    [data-testid="stSidebar"] details summary:hover {
        background-color: rgba(255,255,255,0.05) !important;
    }

    [data-testid="stSidebar"] details summary p {
        color: white !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }

    /* Sidebar Dividers */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1) !important;
    }

    /* Target Streamlit's native containers for the "Card" look */
    /* This styles st.container(border=True) */
    [data-testid="stElementContainer"] > div:has(div.stVerticalBlockBorder) {
        background-color: var(--card-bg) !important;
        border-radius: 15px !important;
        padding: 24px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid rgba(0,0,0,0.03) !important;
        margin-bottom: 20px !important;
    }

    /* KPI Metric Cards (Custom CSS for our HTML injection) */
    .kpi-card {
        background-color: var(--card-bg);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(0,0,0,0.03);
        text-align: left;
        margin-bottom: 15px;
    }
    .kpi-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #6B7280;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .kpi-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: var(--text-dark);
    }

    /* Primary Buttons (Salmon) */
    div.stButton > button:first-child {
        background-color: var(--primary-accent);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #FF765C;
        box-shadow: 0 4px 12px rgba(255, 139, 118, 0.3);
    }

    /* Custom Headers */
    h1, h2, h3 {
        color: var(--text-dark) !important;
        font-weight: 800 !important;
    }

    /* Hide standard Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def render_kpi_card(label, value):
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

# --- User Authentication ---
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'has_unsaved_changes' not in st.session_state:
    st.session_state.has_unsaved_changes = False
if 'saved_manual_targets' not in st.session_state:
    st.session_state['saved_manual_targets'] = {}
if 'show_recommendations' not in st.session_state:
    st.session_state.show_recommendations = False
if 'last_calculation' not in st.session_state:
    st.session_state.last_calculation = None

def clear_recommendations():
    st.session_state.show_recommendations = False
    st.session_state.last_calculation = None

def reset_portfolio_state():
    clear_recommendations()
    if 'portfolio_selector' in st.session_state:
        selected = st.session_state.portfolio_selector
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"{selected}_")]
        for k in keys_to_clear:
            del st.session_state[k]

# Get secrets
admin_hash = os.getenv('ADMIN_PASSWORD_HASH')
cookie_key = os.getenv('COOKIE_KEY')

if not admin_hash or not cookie_key:
    st.error("security configuration missing: ADMIN_PASSWORD_HASH or COOKIE_KEY not found in environment.")
    st.stop()

# Configuration dictionary
config = {
    'credentials': {
        'usernames': {
            'admin': {
                'name': 'Admin User',
                'password': admin_hash,
                'email': 'admin@example.com'
            }
        }
    },
    'cookie': {
        'name': 'portfolio_rebalancer_cookie',
        'key': cookie_key,
        'expiry_days': 30
    },
    'pre-authorized': {'emails': []}
}

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authenticator.login('main')

authentication_status = st.session_state.get('authentication_status')
name = st.session_state.get('name')
username = st.session_state.get('username')

if authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    st.warning('Please enter your username and password')
elif authentication_status:
    with st.sidebar:
        authenticator.logout('Logout', 'main')
        st.write(f'Welcome *{name}*')
        st.divider()

    # --- MAIN APP LOGIC STARTS HERE ---
    st.title("💰 Portfolio Allocation Calculator")
    st.markdown("Calculate optimal investment amounts to rebalance your portfolio")

    # Initialize GSheets connection
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)


    # Load data from Google Sheets into Session State
    if 'master_data' not in st.session_state:
        try:
            # Load with a cache but then move to Session State for "instant" local updates
            raw_data = conn.read(worksheet="Portfolios", ttl="10m") 
            
            if raw_data is None:
                raw_data = pd.DataFrame()
                
            if not raw_data.empty and 'portfolio_name' not in raw_data.columns:
                raw_data['portfolio_name'] = 'Default'
            
            required_columns = ['username', 'stock_name', 'current_value', 'target_allocation', 'portfolio_name']
            
            if raw_data.empty:
                raw_data = pd.DataFrame(columns=required_columns)
            else:
                for col in required_columns:
                    if col not in raw_data.columns:
                        raw_data[col] = pd.NA
                        
                raw_data = raw_data.astype({
                    'username': 'str',
                    'stock_name': 'str', 
                    'current_value': 'float',
                    'target_allocation': 'float',
                    'portfolio_name': 'str'
                })
                raw_data['portfolio_name'] = raw_data['portfolio_name'].fillna('Default')
                raw_data['username'] = raw_data['username'].fillna('unknown') 

            st.session_state.master_data = raw_data

        except Exception as e:
            st.session_state.master_data = pd.DataFrame(columns=['username', 'stock_name', 'current_value', 'target_allocation', 'portfolio_name'])

    data = st.session_state.master_data

    # Filter for current user
    user_all_data = data[data['username'] == username]
    
    # --- Data Filtering & Initialization (Top Level) ---

    # Determine existing portfolios
    if not user_all_data.empty:
        existing_portfolios = sorted(user_all_data['portfolio_name'].unique().tolist())
    else:
        existing_portfolios = []

    # Handle auto-selection after creation
    default_index = 0
    if 'new_portfolio_created' in st.session_state:
        target_new = st.session_state.new_portfolio_created
        if target_new in existing_portfolios:
            default_index = existing_portfolios.index(target_new)
        # We don't delete it yet, we need it for the widget default
    
    # We need a temporary key for the selector to avoid duplication issues if we move it
    selected_portfolio = None
    if existing_portfolios:
        # We peek at the session state to see if there's a selected portfolio already
        # but since we haven't rendered the selectbox yet, we use the logic below.
        pass

    # --- Sidebar UI ---
    with st.sidebar:
        # 1. Portfolios Section
        with st.expander("📂 Portfolios", expanded=True):
            if existing_portfolios:
                selected_portfolio = st.selectbox(
                    "Select Portfolio", 
                    existing_portfolios, 
                    index=default_index, 
                    key="portfolio_selector",
                    on_change=reset_portfolio_state
                )
                # If a new portfolio was just created and we just rendered the selectbox with it, we can clear the flag
                if 'new_portfolio_created' in st.session_state and st.session_state.new_portfolio_created == selected_portfolio:
                    del st.session_state.new_portfolio_created
            else:
                selected_portfolio = None
                st.info("No portfolios found.")
            
            # Create New Portfolio
            with st.expander("Create New Portfolio"):
                new_portfolio_input = st.text_input("Name", placeholder="e.g., Retirement")
                if st.button("Create"):
                    if new_portfolio_input and new_portfolio_input not in existing_portfolios:
                        # Create a placeholder row to persist the portfolio name
                        new_row = pd.DataFrame([{
                            "username": username,
                            "portfolio_name": new_portfolio_input,
                            "stock_name": "__PLACEHOLDER__",
                            "current_value": 0.0,
                            "target_allocation": 0.0
                        }])
                        updated_data = pd.concat([data, new_row], ignore_index=True)
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        
                        st.session_state.new_portfolio_created = new_portfolio_input
                        st.session_state.has_unsaved_changes = False # Just synced
                        reset_portfolio_state()
                        st.success(f"Created '{new_portfolio_input}'!")
                        st.rerun()


            # Rename Portfolio
            if selected_portfolio:
                with st.expander(f"📝 Rename '{selected_portfolio}'"):
                    new_name_input = st.text_input("New Name", placeholder="e.g., Retirement 2026")
                    if st.button("Save New Name"):
                        if new_name_input and new_name_input not in existing_portfolios:
                            # Update all rows in master data
                            mask = (st.session_state.master_data['username'] == username) & \
                                   (st.session_state.master_data['portfolio_name'] == selected_portfolio)
                            
                            st.session_state.master_data.loc[mask, 'portfolio_name'] = new_name_input
                            conn.update(worksheet="Portfolios", data=st.session_state.master_data)
                            
                            st.session_state.new_portfolio_created = new_name_input
                            st.session_state.has_unsaved_changes = False # Just synced
                            reset_portfolio_state()
                            st.success(f"Renamed to '{new_name_input}'!")
                            st.rerun()
                        elif new_name_input in existing_portfolios:
                            st.error("A portfolio with this name already exists.")
                        else:
                            st.error("Please enter a valid name.")

            # Delete Portfolio
            if selected_portfolio:
                with st.expander(f"⚠️ Delete '{selected_portfolio}'"):
                    st.warning("This action cannot be undone.")
                    if st.button("Confirm Delete", type="primary", key="delete_portfolio_btn"):
                        # Remove all rows belonging to this portfolio
                        mask_to_delete = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        updated_data = data[~mask_to_delete]
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        st.session_state.has_unsaved_changes = False # Just synced
                        reset_portfolio_state()
                        st.toast(f"Deleted portfolio: {selected_portfolio}")
                        st.rerun()
        
        pass

    # --- Sync Data Logic (Source of Truth) ---
    # Load current stocks from Master data (Persistent state)
    # This list reflects the state AT THE START of the run.
    user_portfolio_df = user_all_data[user_all_data['portfolio_name'] == selected_portfolio] if selected_portfolio else pd.DataFrame()
    user_portfolio_df = user_portfolio_df[user_portfolio_df['stock_name'] != "__PLACEHOLDER__"] if not user_portfolio_df.empty else pd.DataFrame()

    current_stocks = []
    for _, row in user_portfolio_df.iterrows():
        current_stocks.append({
            "name": row['stock_name'],
            "current_value": row['current_value'],
            "target_allocation": row['target_allocation']
        })
    
    # We store the original values for change detection
    st.session_state.stocks = current_stocks

    # Pre-populate session state keys for widgets if they don't exist
    # This prevents the "Session State API vs Default Value" conflict
    if selected_portfolio:
        for idx, stock in enumerate(current_stocks):
            key_prefix = f"{selected_portfolio}_{idx}"
            if f"{key_prefix}_name" not in st.session_state:
                st.session_state[f"{key_prefix}_name"] = stock['name']
            if f"{key_prefix}_value" not in st.session_state:
                st.session_state[f"{key_prefix}_value"] = float(stock['current_value'])
            if f"{key_prefix}_target" not in st.session_state:
                st.session_state[f"{key_prefix}_target"] = float(stock['target_allocation'])

    # Sidebar utilities (Configuration and Indicators)
    with st.sidebar:
        if selected_portfolio:
            # 2. Configuration Section
            with st.expander("⚙️ Configuration", expanded=False):
                monthly_investment = st.number_input(
                    "Monthly Investment Amount (€)",
                    min_value=0.0,
                    value=1000.0,
                    step=100.0,
                    help="Amount you want to invest this month",
                    on_change=clear_recommendations
                )
                
                # Market Indicators
                st.markdown("### Market Indicators")
                
                # Track state transitions for reverting to manual targets
                if 'prev_indicators_state' not in st.session_state:
                    st.session_state.prev_indicators_state = False
                    
                use_market_indicators = st.checkbox(
                    "Use Market Indicators", 
                    value=st.session_state.prev_indicators_state, 
                    help="Enable rebalancing rules based on Buffett Indicator and CAPE Ratio",
                    on_change=clear_recommendations
                )
                
                # Detect Transition: ON -> OFF
                if not use_market_indicators and st.session_state.prev_indicators_state:
                    if st.session_state.saved_manual_targets.get(selected_portfolio):
                        manual_map = st.session_state.saved_manual_targets[selected_portfolio]
                        
                        # Filter for this portfolio's rows in global 'data'
                        mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        
                        # Update 'data' with manual targets before saving back to DB
                        for stock_name, target in manual_map.items():
                            data.loc[mask & (data['stock_name'] == stock_name), 'target_allocation'] = target
                        
                        st.session_state.master_data = data
                        # Deferred: conn.update(worksheet="Portfolios", data=data)
                        st.session_state.has_unsaved_changes = True
                        
                        # Update session state and widget keys
                        for i, stock in enumerate(st.session_state.stocks):
                            if stock['name'] in manual_map:
                                val = manual_map[stock['name']]
                                st.session_state.stocks[i]['target_allocation'] = val
                                st.session_state[f"{selected_portfolio}_{i}_target"] = val
                        
                        st.session_state.prev_indicators_state = False
                        st.toast("Reverted to manual allocations!", icon="↩️")
                        st.rerun()

                # Update state for next check if it was OFF->ON
                if use_market_indicators and not st.session_state.prev_indicators_state:
                    st.session_state.prev_indicators_state = True
                
                if use_market_indicators:
                    buffett_index = st.number_input(
                        "Buffett Indicator (%)", 
                        value=195.0, 
                        step=0.1, 
                        help="Market Cap to GDP",
                        on_change=clear_recommendations
                    )
                    
                    target_ratios = None
                    phase_name = "Unknown"
                    
                    if buffett_index >= 190.0:
                        target_ratios = [45, 45, 10]
                        phase_name = "Highly Overvalued 🏰"
                    elif 170.0 <= buffett_index < 190.0:
                        target_ratios = [50, 40, 10]
                        phase_name = "Overvalued 🛡️"
                    elif 140.0 <= buffett_index < 170.0:
                        target_ratios = [60, 30, 10]
                        phase_name = "Fair Value ⚖️"
                    elif buffett_index < 140.0:
                        target_ratios = [70, 20, 10]
                        phase_name = "Undervalued 🚀"

                    if target_ratios:
                        st.info(f"Market Status: **{phase_name}** | Target Mix: {target_ratios}")
                        
                        if len(st.session_state.stocks) >= 3:
                            for i in range(3):
                                new_alloc = float(target_ratios[i])
                                st.session_state.stocks[i]['target_allocation'] = new_alloc
                                widget_key = f"{selected_portfolio}_{i}_target"
                                st.session_state[widget_key] = new_alloc
                        else:
                            st.warning("⚠️ Need at least 3 stocks to apply Market Indicator rules.")
                else:
                     buffett_index = 195.0
                     
                     current_targets_map = {}
                     for _, row in user_portfolio_df.iterrows():
                         current_targets_map[row['stock_name']] = float(row['target_allocation'])
                     
                     st.session_state.saved_manual_targets[selected_portfolio] = current_targets_map
            
            # 3. Add Stock Section
            with st.expander("🛠️ Stock Management", expanded=False):
                st.markdown("➕ **Add New Stock**")
                new_name = st.text_input("Stock Name")
                new_value = st.number_input("Current Value (€)", min_value=0.0, value=0.0, key="new_value")
                new_target = st.number_input("Target Allocation (%)", min_value=0.0, max_value=100.0, value=0.0, key="new_target")
                
                if st.button("Add Stock"):
                    if new_name:
                        new_row = pd.DataFrame([{
                            "username": username,
                            "stock_name": new_name,
                            "current_value": new_value,
                            "target_allocation": new_target,
                            "portfolio_name": selected_portfolio
                        }])
                        
                        mask_placeholder = (data['username'] == username) & \
                                         (data['portfolio_name'] == selected_portfolio) & \
                                         (data['stock_name'] == "__PLACEHOLDER__")
                        
                        if mask_placeholder.any():
                            data = data[~mask_placeholder]

                        updated_data = pd.concat([data, new_row], ignore_index=True)
                        st.session_state.master_data = updated_data
                        # Deferred: conn.update(worksheet="Portfolios", data=updated_data)
                        st.session_state.has_unsaved_changes = True
                        reset_portfolio_state()
                        st.success(f"Added {new_name}")
                        st.rerun()
                    else:
                        st.error("Please enter a stock name")
        else:
            monthly_investment = 1000.0 # Default fallback for later logic



    # Main content
    if selected_portfolio:
        # --- Live Calculation Logic ---
        # Synchronize "live" values for calculations (Summary/Recommendations) 
        # using current widget state before saving to GSheets.
        live_stocks = []
        for idx, stock in enumerate(st.session_state.stocks):
            key_prefix = f"{selected_portfolio}_{idx}"
            live_stocks.append({
                "name": st.session_state.get(f"{key_prefix}_name", stock['name']),
                "current_value": st.session_state.get(f"{key_prefix}_value", stock['current_value']),
                "target_allocation": st.session_state.get(f"{key_prefix}_target", stock['target_allocation'])
            })

        # --- Top Row: KPI Cards ---
        total_current = sum(s['current_value'] for s in live_stocks)
        total_target = sum(s['target_allocation'] for s in live_stocks)
        num_stocks = len(live_stocks)
        
        # Dashboard Header
        st.markdown(f"## 📊 {selected_portfolio} Dashboard")
        
        kpi_cols = st.columns(4)
        with kpi_cols[0]: render_kpi_card("Total Value", f"€{total_current:,.2f}")
        with kpi_cols[1]: render_kpi_card("Stocks Count", f"{num_stocks}")
        with kpi_cols[2]: render_kpi_card("Target Spread", f"{total_target:.1f}%")
        with kpi_cols[3]: render_kpi_card("Monthly Budget", f"€{monthly_investment:,.2f}")
        
        if abs(total_target - 100.0) > 0.01:
            st.warning("⚠️ Your target allocations do not sum to 100%. Please adjust them in Portfolio Management.")

        # --- Middle Row: Management & Recommendations ---
        col_main, col_side = st.columns([2, 1])

        with col_main:
            with st.container(border=True):
                st.subheader("📝 Portfolio Management")
                
                if not st.session_state.stocks or (len(st.session_state.stocks) == 1 and st.session_state.stocks[0]['name'] == "__PLACEHOLDER__"):
                    st.info("This portfolio is empty. Add stocks using the sidebar!", icon="👈")
                else:
                    # Headers
                    h_cols = st.columns([3, 2, 2, 1])
                    h_cols[0].markdown("**Ticker**")
                    h_cols[1].markdown("**Value (€)**")
                    h_cols[2].markdown("**Target %**")

                    for idx, stock in enumerate(st.session_state.stocks):
                        if stock['name'] == "__PLACEHOLDER__": continue
                        key_prefix = f"{selected_portfolio}_{idx}"
                        r_cols = st.columns([3, 2, 2, 1])
                        with r_cols[0]:
                            st.text_input("Name", key=f"{key_prefix}_name", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[1]:
                            st.number_input("Value", min_value=0.0, step=100.0, key=f"{key_prefix}_value", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[2]:
                            st.number_input("Target", min_value=0.0, max_value=100.0, step=1.0, key=f"{key_prefix}_target", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[3]:
                            if st.button("🗑️", key=f"{key_prefix}_remove"):
                                filtered_idx = user_portfolio_df.index[idx]
                                remaining_in_portfolio = user_portfolio_df.drop(filtered_idx)
                                if remaining_in_portfolio.empty:
                                    placeholder_row = pd.DataFrame([{"username": username, "portfolio_name": selected_portfolio, "stock_name": "__PLACEHOLDER__", "current_value": 0.0, "target_allocation": 0.0}])
                                    updated_data = pd.concat([data.drop(filtered_idx), placeholder_row], ignore_index=True)
                                else:
                                    updated_data = data.drop(filtered_idx)
                                st.session_state.master_data = updated_data
                                st.session_state.has_unsaved_changes = True
                                reset_portfolio_state()
                                st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Save All Changes", width="stretch"):
                        any_content_changes = False
                        for idx, stock in enumerate(st.session_state.stocks):
                            key_prefix = f"{selected_portfolio}_{idx}"
                            new_name = st.session_state.get(f"{key_prefix}_name")
                            new_val = st.session_state.get(f"{key_prefix}_value")
                            new_target = st.session_state.get(f"{key_prefix}_target")
                            orig_row = user_portfolio_df.iloc[idx]
                            if (new_name != orig_row['stock_name'] or abs(new_val - orig_row['current_value']) > 0.01 or abs(new_target - orig_row['target_allocation']) > 0.01):
                                filtered_idx = user_portfolio_df.index[idx]
                                data.at[filtered_idx, 'stock_name'] = new_name
                                data.at[filtered_idx, 'current_value'] = new_val
                                data.at[filtered_idx, 'target_allocation'] = new_target
                                any_content_changes = True
                        if any_content_changes or st.session_state.has_unsaved_changes:
                            st.session_state.master_data = data
                            conn.update(worksheet="Portfolios", data=data)
                            st.session_state.has_unsaved_changes = False
                            st.success("All changes saved successfully!")
                            st.rerun()

        with col_side:
            with st.container(border=True):
                st.subheader("🎯 Action Center")
                if st.button("🧮 Calculate Allocation", width="stretch"):
                    if abs(sum(s['target_allocation'] for s in live_stocks) - 100.0) > 0.01:
                        st.error("Ratios must sum to 100%")
                    else:
                        total_current = sum(s['current_value'] for s in live_stocks)
                        new_total_theoretical = total_current + monthly_investment
                        stock_gaps = []
                        for stock in live_stocks:
                            target_val = new_total_theoretical * (stock['target_allocation'] / 100.0)
                            gap = target_val - stock['current_value']
                            stock_gaps.append({"Stock": stock['name'], "Target Value": target_val, "Gap": gap, "stock": stock})
                        sorted_gaps = sorted(stock_gaps, key=lambda x: x['Gap'], reverse=True)
                        remaining_investment = monthly_investment
                        allocations = []
                        for item in sorted_gaps:
                            invest = max(0, min(item['Gap'], remaining_investment))
                            remaining_investment -= invest
                            new_val = item['stock']['current_value'] + invest
                            allocations.append({"Stock": item['Stock'], "Current Value": item['stock']['current_value'], "Current %": (item['stock']['current_value'] / total_current * 100) if total_current > 0 else 0, "Target %": item['stock']['target_allocation'], "Target Value": item['Target Value'], "Investment": invest, "New Value": new_val, "New %": (new_val / new_total_theoretical * 100)})
                        st.session_state.last_calculation = {"df": pd.DataFrame(allocations), "monthly_investment": monthly_investment, "remaining": remaining_investment}
                        st.session_state.show_recommendations = True
                
                if st.session_state.show_recommendations:
                    st.divider()
                    calc = st.session_state.last_calculation
                    if calc['remaining'] > 0.01:
                        st.warning(f"Note: €{calc['remaining']:.2f} could not be allocated.")
                    st.success("Allocation Calculated!")

        # --- Bottom Row: Results & Visualization ---
        if st.session_state.show_recommendations:
            with st.container(border=True):
                st.subheader("📋 Investment Recommendations")
                df = st.session_state.last_calculation['df']
                st.dataframe(df.style.format(precision=2), hide_index=True, use_container_width=True)
                
                if st.button("💾 Log to History", width="stretch"):
                    with st.spinner("Logging..."):
                        try:
                            log_rows = df.copy()
                            log_rows['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            log_rows['username'] = username
                            log_rows['portfolio_name'] = selected_portfolio
                            cols_to_log = ['timestamp', 'username', 'portfolio_name', 'Stock', 'Current Value', 'Current %', 'Target %', 'Target Value', 'Investment', 'New Value', 'New %']
                            log_df = log_rows[cols_to_log]
                            try: existing_history = conn.read(worksheet="InvestmentLog", ttl=0)
                            except: existing_history = pd.DataFrame()
                            new_history = pd.concat([existing_history, log_df], ignore_index=True) if existing_history is not None and not existing_history.empty else log_df
                            conn.update(worksheet="InvestmentLog", data=new_history)
                            st.success("Logged!")
                            st.balloons()
                        except Exception as e: st.error(f"Error: {e}")

            # Charts Row
            with st.container(border=True):
                st.subheader("📉 Allocation Visuals")
                df_plot = df.sort_values('Stock')
                chart_col1, chart_col2 = st.columns(2)
                
                dashboard_colors = ['#FF8B76', '#7BD192', '#5EB1FF', '#FFD166', '#06D6A0']
                
                with chart_col1:
                    fig1 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['Current Value'], hole=0.3, marker=dict(colors=dashboard_colors))])
                    fig1.update_layout(title_text="Current Allocation", title_font=dict(size=18), legend=dict(font=dict(size=14)), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig1, width="stretch")
                with chart_col2:
                    fig2 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['New Value'], hole=0.3, marker=dict(colors=dashboard_colors))])
                    fig2.update_layout(title_text="After Investment", title_font=dict(size=18), legend=dict(font=dict(size=14)), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig2, width="stretch")

    else:
        # Welcome Screen
        with st.container(border=True):
            st.markdown('<div style="text-align: center; padding: 30px;">', unsafe_allow_html=True)
            st.markdown("# 👋 Welcome to Your Portfolio Manager")
            st.markdown("### Let's get started with your first investment strategy.")
            st.markdown("""
            1. Use the **sidebar** to create your first portfolio.
            2. Add your favorite stocks and set target weights.
            3. Use our **Market Indicator** intelligence to optimize your risk.
            """)
            if st.button("🚀 Create My First Portfolio Now"):
                st.toast("Check the sidebar to your left!", icon="👈")
            st.markdown('</div>', unsafe_allow_html=True)

    # Footer
    st.markdown(
        """
        <div style='text-align: center; color: #9CA3AF; padding: 20px; font-size: 0.8rem;'>
        💡 <b>Smart Rebalancing:</b> Maintain your risk profile with disciplined allocation.<br>
        <small>Educational purposes only. Always consult a financial advisor.</small>
        </div>
        """,
        unsafe_allow_html=True
    )
