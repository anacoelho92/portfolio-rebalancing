import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Portfolio Allocation Calculator", page_icon="💰", layout="wide")

# --- User Authentication ---
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None

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

    # Load data from Google Sheets
    try:
        data = conn.read(worksheet="Portfolios", ttl="0") # ttl=0 for fresh data
        
        # Ensure data is a DataFrame (read can sometimes return unexpected types if empty)
        if data is None:
            data = pd.DataFrame()
            
        # Ensure 'portfolio_name' column exists (migration)
        if not data.empty and 'portfolio_name' not in data.columns:
            data['portfolio_name'] = 'Default'
        
        # Ensure consistency by defining all required columns
        required_columns = ['username', 'stock_name', 'current_value', 'target_allocation', 'portfolio_name']
        
        # If empty or missing crucial columns, enforce structure
        if data.empty:
            data = pd.DataFrame(columns=required_columns)
        else:
            # Add any missing columns with NA
            for col in required_columns:
                if col not in data.columns:
                    data[col] = pd.NA
                    
            # Ensure correct types
            data = data.astype({
                'username': 'str',
                'stock_name': 'str', 
                'current_value': 'float',
                'target_allocation': 'float',
                'portfolio_name': 'str'
            })
            
            # Fill NaNs specifically for key grouping columns to allow filtering
            data['portfolio_name'] = data['portfolio_name'].fillna('Default')
            data['username'] = data['username'].fillna('unknown') 

    except Exception as e:
        # Fallback if connection fails entirely
        # st.error(f"Error loading data: {e}") # Optional: show error to user?
        data = pd.DataFrame(columns=['username', 'stock_name', 'current_value', 'target_allocation', 'portfolio_name'])

    # Filter for current user
    user_all_data = data[data['username'] == username]
    
    # --- Sidebar UI ---
    with st.sidebar:
        # 1. Portfolios Section
        st.header("📂 Portfolios")
        
        # Determine existing portfolios
        if not user_all_data.empty:
            existing_portfolios = sorted(user_all_data['portfolio_name'].unique().tolist())
        else:
            existing_portfolios = []
        
        if "Default" not in existing_portfolios:
            existing_portfolios.insert(0, "Default")
            
        # Handle auto-selection after creation
        default_index = 0
        if 'new_portfolio_created' in st.session_state:
            target_new = st.session_state.new_portfolio_created
            if target_new in existing_portfolios:
                default_index = existing_portfolios.index(target_new)
            del st.session_state.new_portfolio_created
            
        # Selection Dropdown
        selected_portfolio = st.selectbox("Select Portfolio", existing_portfolios, index=default_index, key="portfolio_selector")
        
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
                    conn.update(worksheet="Portfolios", data=updated_data)
                    
                    st.session_state.new_portfolio_created = new_portfolio_input
                    st.success(f"Created '{new_portfolio_input}'!")
                    st.rerun()

        # Delete Portfolio (only for non-Default)
        if selected_portfolio != "Default":
            st.markdown("---")
            with st.expander(f"⚠️ Delete '{selected_portfolio}'"):
                st.warning("This action cannot be undone.")
                if st.button("Confirm Delete", type="primary", key="delete_portfolio_btn"):
                    # Remove all rows belonging to this portfolio
                    mask_to_delete = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                    data = data[~mask_to_delete]
                    conn.update(worksheet="Portfolios", data=data)
                    st.toast(f"Deleted portfolio: {selected_portfolio}")
                    st.rerun()

        st.divider()

        # 2. Configuration Section
        st.header("⚙️ Configuration")
        monthly_investment = st.number_input(
            "Monthly Investment Amount (€)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            help="Amount you want to invest this month"
        )
        
        st.divider()

        # 3. Add Stock Section
        st.header("Manage Stocks")
        with st.expander("➕ Add New Stock"):
            new_name = st.text_input("Stock Name")
            new_value = st.number_input("Current Value (€)", min_value=0.0, value=0.0, key="new_value")
            new_target = st.number_input("Target Allocation (%)", min_value=0.0, max_value=100.0, value=0.0, key="new_target")
            
            if st.button("Add Stock"):
                if new_name:
                    # null checks or cleaning logic could go here
                    
                    # Add to master dataframe
                    # If this is the first real stock, we can optionally remove the placeholder if it exists,
                    # but keeping it is harmless if we always filter it out. 
                    # Actually, let's remove it to keep sheet clean.
                    
                    # Create new row
                    new_row = pd.DataFrame([{
                        "username": username,
                        "stock_name": new_name,
                        "current_value": new_value,
                        "target_allocation": new_target,
                        "portfolio_name": selected_portfolio
                    }])
                    
                    # Remove placeholder if it exists for this portfolio
                    # (Logic: drop rows where portfolio=current AND name=__PLACEHOLDER__)
                    mask_placeholder = (data['username'] == username) & \
                                     (data['portfolio_name'] == selected_portfolio) & \
                                     (data['stock_name'] == "__PLACEHOLDER__")
                    
                    if mask_placeholder.any():
                        data = data[~mask_placeholder]

                    updated_data = pd.concat([data, new_row], ignore_index=True)
                    conn.update(worksheet="Portfolios", data=updated_data)
                    st.success(f"Added {new_name}")
                    st.rerun()
                else:
                    st.error("Please enter a stock name")


    # --- Data Logic (Filtering & State) ---
    # Filter data for SELECTED portfolio
    user_portfolio_df = user_all_data[user_all_data['portfolio_name'] == selected_portfolio]
    
    # Filter out placeholders
    user_portfolio_df = user_portfolio_df[user_portfolio_df['stock_name'] != "__PLACEHOLDER__"]

    # If user has no data in Default portfolio, initialize defaults
    # (Check against raw data including placeholders to avoid re-initializing if user just deleted all real stocks)
    has_any_data_in_portfolio = not user_all_data[user_all_data['portfolio_name'] == selected_portfolio].empty
    
    if selected_portfolio == "Default" and not has_any_data_in_portfolio and user_all_data[user_all_data['portfolio_name'] != "Default"].empty:
        default_stocks = [
            {"username": username, "portfolio_name": "Default", "stock_name": "Stock A", "current_value": 1000.0, "target_allocation": 30.0},
            {"username": username, "portfolio_name": "Default", "stock_name": "Stock B", "current_value": 1500.0, "target_allocation": 40.0},
            {"username": username, "portfolio_name": "Default", "stock_name": "Stock C", "current_value": 500.0, "target_allocation": 30.0},
        ]
        new_rows = pd.DataFrame(default_stocks)
        data = pd.concat([data, new_rows], ignore_index=True)
        conn.update(worksheet="Portfolios", data=data)
        st.toast("Initialized default portfolio!", icon="🌱")
        user_portfolio_df = new_rows # Update local view

    # Convert to list of dicts for session state logic interaction
    current_stocks = []
    for _, row in user_portfolio_df.iterrows():
        current_stocks.append({
            "name": row['stock_name'],
            "current_value": row['current_value'],
            "target_allocation": row['target_allocation']
        })
    
    st.session_state.stocks = current_stocks

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 Current Portfolio")
        
        if not st.session_state.stocks:
            st.info("This portfolio is empty. Add stocks using the sidebar!", icon="👈")
        
        # Display and edit stocks
        stocks_to_remove = []
        
        # We iterate over the LIST (st.session_state.stocks) which reflects current DB state
        # But for edits, we need to identify the exact row in the original dataframe to update
        # Headers
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
                        value=stock['name'],
                        key=f"{key_prefix}_name",
                        label_visibility="collapsed"
                    )
                
                with cols[1]:
                    new_val_val = st.number_input(
                        "Current Value",
                        min_value=0.0,
                        value=float(stock['current_value']),
                        step=100.0,
                        key=f"{key_prefix}_value",
                        label_visibility="collapsed"
                    )
                
                with cols[2]:
                    new_target_val = st.number_input(
                        "Target %",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(stock['target_allocation']),
                        step=1.0,
                        key=f"{key_prefix}_target",
                        label_visibility="collapsed"
                    )
                
                # Check for changes & Save immediately
                if (new_name_val != stock['name'] or 
                    abs(new_val_val - stock['current_value']) > 0.01 or 
                    abs(new_target_val - stock['target_allocation']) > 0.01):
                    
                    # Update the specific row in the main `data` dataframe
                    # Find the row index in the FILTERED dataframe (user_portfolio_df)
                    filtered_idx = user_portfolio_df.index[idx]
                    
                    data.at[filtered_idx, 'stock_name'] = new_name_val
                    data.at[filtered_idx, 'current_value'] = new_val_val
                    data.at[filtered_idx, 'target_allocation'] = new_target_val
                    
                    conn.update(worksheet="Portfolios", data=data)
                    st.rerun()

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
                             # Note: We must drop from the ORIGINAL data here, not the already-dropped one if we had dropped earlier.
                             # But now we only drop here.
                             data = pd.concat([data.drop(filtered_idx), placeholder_row], ignore_index=True)
                        else:
                             data = data.drop(filtered_idx)

                        conn.update(worksheet="Portfolios", data=data)
                        st.rerun()
    
    st.markdown("---")

    with col2:
        st.subheader("📈 Summary")
        
        total_current = sum(s['current_value'] for s in st.session_state.stocks)
        total_target = sum(s['target_allocation'] for s in st.session_state.stocks)
        
        st.metric("Total Portfolio Value", f"€{total_current:,.2f}")
        st.metric("Total Target Allocation", f"{total_target:.1f}%")
        
        if abs(total_target - 100.0) > 0.01:
            st.warning(f"⚠️ Target allocations should sum to 100%")

    # Calculate allocations
    if st.button("🧮 Calculate Investment Allocation", type="primary", width="stretch"):
        if abs(sum(s['target_allocation'] for s in st.session_state.stocks) - 100.0) > 0.01:
            st.error("Please ensure target allocations sum to 100%")
        else:
            st.markdown("---")
            st.subheader("💡 Investment Recommendations")
            
            # --- Advanced Rebalancing Logic (Future Target Approach) ---
            # 1. Rules: No Sell, Integer Investment
            # 2. Strategy: Aim for Target Allocation of the *Future* Total Portfolio Value.
            #    This ensures "distribute to all" behavior when cash is added, while still correcting imbalances.
            
            total_current = sum(s['current_value'] for s in st.session_state.stocks)
            new_total_theoretical = total_current + monthly_investment
            
            # Calculate the "Ideal" ending value for each stock
            # and the "Gap" (how much we need to buy to reach it)
            allocations_raw = {}
            total_gap = 0.0
            
            stock_gaps = []
            
            for stock in st.session_state.stocks:
                ideal_value = new_total_theoretical * (stock['target_allocation'] / 100.0)
                gap = ideal_value - stock['current_value']
                
                # Enforce No Sell (negative gap becomes 0)
                if gap < 0:
                    gap = 0.0
                
                stock_gaps.append({
                    "name": stock['name'],
                    "gap": gap,
                    "target": stock['target_allocation']
                })
                total_gap += gap

            # Distribute Investment
            allocations = {}
            
            if total_gap > 0:
                # We have gaps to fill. Distribute proportional to the gap.
                # If Total Gap > Monthly Investment (e.g. huge underweights), this partially fills them.
                # If Total Gap < Monthly Investment (e.g. we have extra cash), this logic needs adjustment?
                # Actually, "Ideal Value" was calculated based on (Current + Inv), so 
                # Sum(Ideal) = Current + Inv.
                # Sum(Gap) = Sum(Ideal) - Sum(Current) = Inv.
                # So mathematically, Total Gap should exactly equal Monthly Investment 
                # (unless some gaps were negative/no-sell, then Total Gap < Monthly Inv).
                
                # Case 1: No Sells needed. Total Gap == Monthly Inv. 
                # Allocation is exactly the gap.
                
                # Case 2: Some Sells "ignored" (Gap set to 0). Total Gap > Monthly Inv? 
                # No. Ideal = 1440. Current = 440. Sum(Ideal - Current) = 1000.
                # If we clamp negatives to 0, Sum(Gap) will be GREATER than 1000?
                # Example: A=1000(Ideal 720), B=200(Ideal 720). Inv=240. Future=1440.
                # Gap A = -280 -> 0. Gap B = 520. 
                # Total Gap = 520. We have only 240.
                # So we distribute 240 proportional to the positive gaps.
                
                for s in stock_gaps:
                    if total_gap > 0:
                        allocations[s['name']] = (s['gap'] / total_gap) * monthly_investment
                    else:
                        allocations[s['name']] = 0
            else:
                # Fallback (e.g. everything was perfect or confusing state): Distribute by target
                for stock in st.session_state.stocks:
                    allocations[stock['name']] = monthly_investment * (stock['target_allocation'] / 100.0)

            # --- Integer Constraint Logic ---
            # 1. Floor all allocations
            integer_allocations = {k: int(v) for k, v in allocations.items()}
            
            # 2. Calculate remainder
            current_sum = sum(integer_allocations.values())
            remainder = int(monthly_investment - current_sum)
            
            # 3. Distribute remainder to stocks with highest fractional parts
            if remainder > 0:
                # Calculate fractional parts
                fractionals = []
                for k, v in allocations.items():
                    frac = v - int(v)
                    fractionals.append((k, frac))
                
                # Sort by fractional part descending
                fractionals.sort(key=lambda x: x[1], reverse=True)
                
                # Distribute 1 by 1
                for i in range(remainder):
                    idx = i % len(fractionals)
                    stock_name = fractionals[idx][0]
                    integer_allocations[stock_name] += 1
            
            # Prepare results table
            results = []
            final_actual_new_total = total_current + monthly_investment
            
            for stock in st.session_state.stocks:
                inv_amount = integer_allocations[stock['name']]
                
                current_alloc = (stock['current_value'] / total_current * 100) if total_current > 0 else 0
                
                # Calculate new state
                new_val = stock['current_value'] + inv_amount
                new_alloc = (new_val / final_actual_new_total * 100) if final_actual_new_total > 0 else 0
                
                target_val_approx = final_actual_new_total * (stock['target_allocation'] / 100)
                
                results.append({
                    "Stock": stock['name'],
                    "Current Value": stock['current_value'],
                    "Current %": current_alloc,
                    "Target %": stock['target_allocation'],
                    "Target Value": target_val_approx,
                    "Investment": inv_amount,
                    "New Value": new_val,
                    "New %": new_alloc
                })
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            
            # Display results table
            st.dataframe(
                df.style.format({
                    "Current Value": "€{:,.2f}",
                    "Current %": "{:.2f}%",
                    "Target %": "{:.2f}%",
                    "Target Value": "€{:,.2f}",
                    "Investment": "€{:,.2f}",
                    "New Value": "€{:,.2f}",
                    "New %": "{:.2f}%"
                }),
                width="stretch",
                hide_index=True
            )
            
            # Show total investment
            total_investment = df['Investment'].sum()
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Investment", f"€{total_investment:,.2f}")
            with col_b:
                st.metric("Available to Invest", f"€{monthly_investment:,.2f}")
            with col_c:
                remaining = monthly_investment - total_investment
                st.metric("Remaining/Excess", f"€{remaining:,.2f}", delta=f"{remaining:,.2f}")
            
            if total_investment > monthly_investment:
                st.warning(f"⚠️ Calculated investment (€{total_investment:,.2f}) exceeds available amount (€{monthly_investment:,.2f}). Consider adjusting your targets or increasing investment amount.")
            
            # Visualization
            st.markdown("---")
            st.subheader("📊 Allocation Comparison")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Current allocation pie chart
                fig1 = go.Figure(data=[go.Pie(
                    labels=df['Stock'],
                    values=df['Current Value'],
                    hole=0.3,
                    textfont=dict(size=18),
                    marker=dict(colors=px.colors.qualitative.D3)
                )])
                fig1.update_layout(
                    height=450,
                    title_text="Current Allocation",
                    title_font_size=24,
                    legend=dict(font=dict(size=16))
                )
                st.plotly_chart(fig1, width="stretch")
            
            with col_chart2:
                # New allocation pie chart
                fig2 = go.Figure(data=[go.Pie(
                    labels=df['Stock'],
                    values=df['New Value'],
                    hole=0.3,
                    textfont=dict(size=18),
                    marker=dict(colors=px.colors.qualitative.D3)
                )])
                fig2.update_layout(
                    height=450,
                    title_text="After Investment",
                    title_font_size=24,
                    legend=dict(font=dict(size=16))
                )
                st.plotly_chart(fig2, width="stretch")

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
