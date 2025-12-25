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
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"📊 Portfolio: {selected_portfolio}")
            
            if not st.session_state.stocks:
                st.info("This portfolio is empty. Add stocks using the sidebar!", icon="👈")
            
            # Display and edit stocks
            stocks_to_remove = []
            
            # We iterate over the LIST (st.session_state.stocks) which reflects current DB state
            # But for edits, we need to identify the exact row in the original dataframe to update
            # Headers
            if st.session_state.stocks:
                with st.container():
                    cols = st.columns([3, 2, 2, 1])
                    cols[0].markdown("**Ticker**")
                    cols[1].markdown("**Current Value (€)**")
                    cols[2].markdown("**Target %**")

                for idx, stock in enumerate(st.session_state.stocks):
                    with st.container():
                        cols = st.columns([3, 2, 2, 1])
                        
                        # Namespaced keys to prevent state collision between portfolios
                        key_prefix = f"{selected_portfolio}_{idx}"
                        
                        with cols[0]:
                            new_name_val = st.text_input(
                                "Name",
                                key=f"{key_prefix}_name",
                                label_visibility="collapsed",
                                on_change=clear_recommendations
                            )
                        
                        with cols[1]:
                            new_val_val = st.number_input(
                                "Current Value",
                                min_value=0.0,
                                step=100.0,
                                key=f"{key_prefix}_value",
                                label_visibility="collapsed",
                                on_change=clear_recommendations
                            )
                        
                        with cols[2]:
                            new_target_val = st.number_input(
                                "Target %",
                                min_value=0.0,
                                max_value=100.0,
                                step=1.0,
                                key=f"{key_prefix}_target",
                                label_visibility="collapsed",
                                on_change=clear_recommendations
                            )
                        
                        # Check for changes & Save immediately (REMOVED: causes focus loss)
                        # We now use a bulk save button at the bottom

                        with cols[3]:
                            if st.button("🗑️", key=f"{key_prefix}_remove"):
                                filtered_idx = user_portfolio_df.index[idx]
                                
                                # Check if this deletion makes the portfolio empty
                                remaining_in_portfolio = user_portfolio_df.drop(filtered_idx)
                                if remaining_in_portfolio.empty:
                                     placeholder_row = pd.DataFrame([{
                                        "username": username,
                                        "portfolio_name": selected_portfolio,
                                        "stock_name": "__PLACEHOLDER__",
                                        "current_value": 0.0,
                                        "target_allocation": 0.0
                                    }])
                                     updated_data = pd.concat([data.drop(filtered_idx), placeholder_row], ignore_index=True)
                                else:
                                     updated_data = data.drop(filtered_idx)

                                st.session_state.master_data = updated_data
                                # Deferred: conn.update(worksheet="Portfolios", data=updated_data)
                                st.session_state.has_unsaved_changes = True
                                reset_portfolio_state()
                                st.rerun()

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
            
            # NOTE: We do NOT override st.session_state.stocks here because we need it
            # to detect changes in the "Save" block below.

            # Bulk Save Button for Edits
            if st.session_state.stocks or st.session_state.has_unsaved_changes:
                if st.button("💾 Save All Changes", type="primary", width="stretch"):
                    any_content_changes = False
                    for idx, stock in enumerate(st.session_state.stocks):
                        key_prefix = f"{selected_portfolio}_{idx}"
                        
                        # Fetch current values from session state / widget keys
                        # We compare against user_portfolio_df which reflects the last SAVED state
                        orig_row = user_portfolio_df.iloc[idx]
                        new_name = st.session_state.get(f"{key_prefix}_name", orig_row['stock_name'])
                        new_val = st.session_state.get(f"{key_prefix}_value", orig_row['current_value'])
                        new_target = st.session_state.get(f"{key_prefix}_target", orig_row['target_allocation'])
                        
                        if (new_name != orig_row['stock_name'] or 
                            abs(new_val - orig_row['current_value']) > 0.01 or 
                            abs(new_target - orig_row['target_allocation']) > 0.01):
                            
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
                    else:
                        st.info("No changes detected.")
        
        st.markdown("---")

        with col2:
            st.subheader("📈 Summary")
            
            total_current = sum(s['current_value'] for s in live_stocks)
            total_target = sum(s['target_allocation'] for s in live_stocks)
            
            st.metric("Total Portfolio Value", f"€{total_current:,.2f}")
            st.metric("Total Target Allocation", f"{total_target:.1f}%")
            
            if abs(total_target - 100.0) > 0.01:
                st.warning(f"⚠️ Target allocations should sum to 100%")

        # Calculate allocations
        if st.button("🧮 Calculate Investment Allocation", type="primary", width="stretch"):
            if abs(sum(s['target_allocation'] for s in live_stocks) - 100.0) > 0.01:
                st.error("Please ensure target allocations sum to 100%")
            else:
                total_current = sum(s['current_value'] for s in live_stocks)
                new_total_theoretical = total_current + monthly_investment
                
                stock_gaps = []
                total_gap = 0.0
                for stock in live_stocks:
                    ideal_value = new_total_theoretical * (stock['target_allocation'] / 100.0)
                    gap = max(0.0, ideal_value - stock['current_value'])
                    stock_gaps.append({"name": stock['name'], "gap": gap, "target": stock['target_allocation'], "current_val": stock['current_value']})
                    total_gap += gap
                
                ratios = [s['current_value'] / (s['target_allocation'] / 100.0) for s in live_stocks if s['target_allocation'] > 0]
                cash_needed_total = max(0.0, max(ratios) - total_current) if ratios else 0.0

                allocations = {s['name']: (s['gap'] / total_gap * monthly_investment) if total_gap > 0 else (monthly_investment * s['target_allocation'] / 100.0) for s in stock_gaps}
                integer_allocations = {k: int(v) for k, v in allocations.items()}
                remainder = int(monthly_investment - sum(integer_allocations.values()))
                if remainder > 0:
                    fractionals = sorted([(k, v - int(v)) for k, v in allocations.items()], key=lambda x: x[1], reverse=True)
                    for i in range(remainder):
                        integer_allocations[fractionals[i % len(fractionals)][0]] += 1
                
                results = []
                final_total = total_current + monthly_investment
                for stock in live_stocks:
                    inv = integer_allocations[stock['name']]
                    new_val = stock['current_value'] + inv
                    results.append({
                        "Stock": stock['name'],
                        "Current Value": stock['current_value'], "Current %": (stock['current_value'] / total_current * 100) if total_current > 0 else 0,
                        "Target %": stock['target_allocation'], "Target Value": final_total * (stock['target_allocation'] / 100),
                        "Investment": inv, "New Value": new_val, "New %": (new_val / final_total * 100) if final_total > 0 else 0,
                        "Deviation": (new_val / final_total * 100 if final_total > 0 else 0) - stock['target_allocation']
                    })
                
                st.session_state.last_calculation = {
                    "df": pd.DataFrame(results),
                    "total_investment": sum(integer_allocations.values()),
                    "cash_needed_total": cash_needed_total,
                    "monthly_investment": monthly_investment
                }
                st.session_state.show_recommendations = True

        if st.session_state.get('show_recommendations') and st.session_state.last_calculation:
            calc = st.session_state.last_calculation
            df = calc["df"]
            
            st.markdown("---")
            st.subheader("💡 Investment Recommendations")
            
            st.dataframe(df.style.format({
                "Current Value": "€{:,.2f}", "Current %": "{:.2f}%", "Target %": "{:.2f}%",
                "Target Value": "€{:,.2f}", "Investment": "€{:,.2f}", "New Value": "€{:,.2f}",
                "New %": "{:.2f}%", "Deviation": "{:+.2f}%"
            }), width="stretch", hide_index=True)
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Investment", f"€{calc['total_investment']:,.2f}")
            col_b.metric("Available to Invest", f"€{calc['monthly_investment']:,.2f}")
            rem = calc['monthly_investment'] - calc['total_investment']
            col_c.metric("Remaining/Excess", f"€{rem:,.2f}", delta=f"{rem:,.2f}")
            
            if calc['total_investment'] > calc['monthly_investment']:
                st.warning(f"⚠️ Calculated investment (€{calc['total_investment']:,.2f}) exceeds available amount.")
            
            if calc['cash_needed_total'] > calc['monthly_investment']:
                st.info(f"💡 **Insight:** To perfectly rebalance without selling, you would need **€{calc['cash_needed_total']:,.2f}**.")
            elif calc['cash_needed_total'] > 0:
                st.success(f"✅ **Insight:** Your €{calc['monthly_investment']:,.2f} is sufficient to fully rebalance.")

            # --- Save to History ---
            if st.button("💾 Save to Investment History", type="primary", width="stretch"):
                with st.spinner("Logging investment..."):
                    try:
                        # Prepare data for history log
                        log_rows = df.copy()
                        log_rows['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_rows['username'] = username
                        log_rows['portfolio_name'] = selected_portfolio
                        
                        # Reorder columns for better readability in GSheets
                        cols = ['timestamp', 'username', 'portfolio_name', 'Stock', 'Current Value', 'Current %', 'Target %', 'Target Value', 'Investment', 'New Value', 'New %', 'Deviation']
                        log_df = log_rows[cols]
                        
                        # Read existing history to append
                        try:
                            # We use a very short TTL to ensure we get the latest for appending
                            existing_history = conn.read(worksheet="InvestmentLog", ttl=0)
                        except Exception:
                            existing_history = pd.DataFrame()
                        
                        if existing_history is not None and not existing_history.empty:
                            new_history = pd.concat([existing_history, log_df], ignore_index=True)
                        else:
                            new_history = log_df
                        
                        # Update the worksheet
                        conn.update(worksheet="InvestmentLog", data=new_history)
                        st.success("Investment successfully logged to 'InvestmentLog' sheet!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Failed to save history: {e}")

            st.markdown("---")
            st.subheader("📊 Allocation Comparison")
            
            # Sort alphabetically for consistent plot order
            df_plot = df.sort_values('Stock')
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                fig1 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['Current Value'], hole=0.3)])
                fig1.update_layout(
                    title_text="Current Allocation",
                    title_font=dict(size=22),
                    legend=dict(font=dict(size=16)),
                    font=dict(size=14)
                )
                st.plotly_chart(fig1, width="stretch")
            with col_chart2:
                fig2 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['New Value'], hole=0.3)])
                fig2.update_layout(
                    title_text="After Investment",
                    title_font=dict(size=22),
                    legend=dict(font=dict(size=16)),
                    font=dict(size=14)
                )
                st.plotly_chart(fig2, width="stretch")

    else:
        # Welcome Screen
        st.info("👋 **Welcome!** You don't have any portfolios yet.")
        st.markdown("""
        ### Getting Started:
        1. Use the **sidebar** on the left to create your first portfolio (e.g., 'Retirement' or 'Savings').
        2. Once created, you can add stocks and define your target allocations.
        3. The calculator will help you decide exactly how much to invest in each stock to reach your goals.
        """)
        
        # Optional: Add a button here that opens the sidebar or just a message
        if st.button("🚀 Create My First Portfolio Now"):
            st.toast("Check the sidebar to your left!", icon="👈")

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; padding: 20px;'>
        💡 <b>Tip:</b> Regular rebalancing helps maintain your desired risk profile<br>
        <small>This tool is for educational purposes. Always consult with a financial advisor.</small>
        </div>
        """,
        unsafe_allow_html=True
    )
