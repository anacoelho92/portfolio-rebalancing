import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
        # Ensure correct types
        if not data.empty:
            data = data.astype({
                'username': 'str',
                'stock_name': 'str', 
                'current_value': 'float',
                'target_allocation': 'float'
            })
    except Exception:
        # If sheet is empty or fails, create empty dataframe
        data = pd.DataFrame(columns=['username', 'stock_name', 'current_value', 'target_allocation'])

    # Filter for current user
    user_stocks_df = data[data['username'] == username]

    # If user has no data, initialize with defaults AND save to sheet immediately to bootstrap
    if user_stocks_df.empty:
        default_stocks = [
            {"username": username, "stock_name": "Stock A", "current_value": 1000.0, "target_allocation": 30.0},
            {"username": username, "stock_name": "Stock B", "current_value": 1500.0, "target_allocation": 40.0},
            {"username": username, "stock_name": "Stock C", "current_value": 500.0, "target_allocation": 30.0},
        ]
        new_rows = pd.DataFrame(default_stocks)
        data = pd.concat([data, new_rows], ignore_index=True)
        conn.update(worksheet="Portfolios", data=data)
        st.toast("Initialized default portfolio!", icon="🌱")
        user_stocks_df = new_rows # Update local view

    # Convert to list of dicts for session state logic interaction (preserving existing UI logic)
    # We map 'stock_name' back to 'name' for the UI
    current_stocks = []
    for _, row in user_stocks_df.iterrows():
        current_stocks.append({
            "name": row['stock_name'],
            "current_value": row['current_value'],
            "target_allocation": row['target_allocation']
        })
    
    # We use session state as a temporary buffer for edits, but we overwrite it with DB data on load
    st.session_state.stocks = current_stocks

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        monthly_investment = st.number_input(
            "Monthly Investment Amount ($)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            help="Amount you want to invest this month"
        )
        
        st.markdown("---")
        st.subheader("Manage Stocks")
        
        # Add new stock
        with st.expander("➕ Add New Stock"):
            new_name = st.text_input("Stock Name")
            new_value = st.number_input("Current Value ($)", min_value=0.0, value=0.0, key="new_value")
            new_target = st.number_input("Target Allocation (%)", min_value=0.0, max_value=100.0, value=0.0, key="new_target")
            
            if st.button("Add Stock"):
                if new_name:
                    # Add to master dataframe
                    new_row = pd.DataFrame([{
                        "username": username,
                        "stock_name": new_name,
                        "current_value": new_value,
                        "target_allocation": new_target
                    }])
                    updated_data = pd.concat([data, new_row], ignore_index=True)
                    conn.update(worksheet="Portfolios", data=updated_data)
                    st.success(f"Added {new_name}")
                    st.rerun()
                else:
                    st.error("Please enter a stock name")

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 Current Portfolio")
        
        # Display and edit stocks
        stocks_to_remove = []
        
        # We iterate over the LIST (st.session_state.stocks) which reflects current DB state
        # But for edits, we need to identify the exact row in the original dataframe to update
        
        for idx, stock in enumerate(st.session_state.stocks):
            with st.container():
                cols = st.columns([3, 2, 2, 1])
                
                # We simply use the UI to gather new values
                # Then we perform a bulk update logic if changed
                
                with cols[0]:
                    new_name_val = st.text_input(
                        "Name",
                        value=stock['name'],
                        key=f"name_{idx}",
                        label_visibility="collapsed"
                    )
                
                with cols[1]:
                    new_val_val = st.number_input(
                        "Current Value",
                        min_value=0.0,
                        value=float(stock['current_value']),
                        step=100.0,
                        key=f"value_{idx}",
                        label_visibility="collapsed"
                    )
                
                with cols[2]:
                    new_target_val = st.number_input(
                        "Target %",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(stock['target_allocation']),
                        step=1.0,
                        key=f"target_{idx}",
                        label_visibility="collapsed"
                    )
                
                # Check for changes & Save immediately
                # This is a bit inefficient (one write per change) but simpler for Streamlit mechanics
                # Identifying the row: We assume (username, stock_name) is unique-ish for simplicity, 
                # but relying on `idx` relative to the filtered dataframe is safer if order is preserved.
                
                # Logic: If values changed from what is in `stock`, update DB
                if (new_name_val != stock['name'] or 
                    abs(new_val_val - stock['current_value']) > 0.01 or 
                    abs(new_target_val - stock['target_allocation']) > 0.01):
                    
                    # Update the specific row in the main `data` dataframe
                    # Find the row index in the FILTERED dataframe
                    filtered_idx = user_stocks_df.index[idx]
                    
                    data.at[filtered_idx, 'stock_name'] = new_name_val
                    data.at[filtered_idx, 'current_value'] = new_val_val
                    data.at[filtered_idx, 'target_allocation'] = new_target_val
                    
                    conn.update(worksheet="Portfolios", data=data)
                    # No rerun needed here, the loop continues, but the validation logic below will catch it
                    # actually st.rerun() is safer to refresh the view
                    st.rerun()

                with cols[3]:
                    if st.button("🗑️", key=f"remove_{idx}"):
                        filtered_idx = user_stocks_df.index[idx]
                        data = data.drop(filtered_idx)
                        conn.update(worksheet="Portfolios", data=data)
                        st.rerun()
    
    st.markdown("---")

    with col2:
        st.subheader("📈 Summary")
        
        total_current = sum(s['current_value'] for s in st.session_state.stocks)
        total_target = sum(s['target_allocation'] for s in st.session_state.stocks)
        
        st.metric("Total Portfolio Value", f"${total_current:,.2f}")
        st.metric("Total Target Allocation", f"{total_target:.1f}%")
        
        if abs(total_target - 100.0) > 0.01:
            st.warning(f"⚠️ Target allocations should sum to 100%")

    # Calculate allocations
    if st.button("🧮 Calculate Investment Allocation", type="primary", use_container_width=True):
        if abs(sum(s['target_allocation'] for s in st.session_state.stocks) - 100.0) > 0.01:
            st.error("Please ensure target allocations sum to 100%")
        else:
            st.markdown("---")
            st.subheader("💡 Investment Recommendations")
            
            # Calculate new portfolio value after investment
            new_total = total_current + monthly_investment
            
            # Calculate target values
            results = []
            for stock in st.session_state.stocks:
                target_value = new_total * (stock['target_allocation'] / 100)
                investment_needed = target_value - stock['current_value']
                current_allocation = (stock['current_value'] / total_current * 100) if total_current > 0 else 0
                new_allocation = (target_value / new_total * 100) if new_total > 0 else 0
                
                results.append({
                    "Stock": stock['name'],
                    "Current Value": stock['current_value'],
                    "Current %": current_allocation,
                    "Target %": stock['target_allocation'],
                    "Target Value": target_value,
                    "Investment": max(0, investment_needed),  # Don't show negative investments
                    "New Value": stock['current_value'] + max(0, investment_needed),
                    "New %": new_allocation
                })
            
            df = pd.DataFrame(results)
            
            # Display results table
            st.dataframe(
                df.style.format({
                    "Current Value": "${:,.2f}",
                    "Current %": "{:.2f}%",
                    "Target %": "{:.2f}%",
                    "Target Value": "${:,.2f}",
                    "Investment": "${:,.2f}",
                    "New Value": "${:,.2f}",
                    "New %": "{:.2f}%"
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Show total investment
            total_investment = df['Investment'].sum()
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Investment", f"${total_investment:,.2f}")
            with col_b:
                st.metric("Available to Invest", f"${monthly_investment:,.2f}")
            with col_c:
                remaining = monthly_investment - total_investment
                st.metric("Remaining/Excess", f"${remaining:,.2f}", delta=f"{remaining:,.2f}")
            
            if total_investment > monthly_investment:
                st.warning(f"⚠️ Calculated investment (${total_investment:,.2f}) exceeds available amount (${monthly_investment:,.2f}). Consider adjusting your targets or increasing investment amount.")
            
            # Visualization
            st.markdown("---")
            st.subheader("📊 Allocation Comparison")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Current allocation pie chart
                fig1 = go.Figure(data=[go.Pie(
                    labels=df['Stock'],
                    values=df['Current Value'],
                    title="Current Allocation",
                    hole=0.3
                )])
                fig1.update_layout(height=300)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col_chart2:
                # New allocation pie chart
                fig2 = go.Figure(data=[go.Pie(
                    labels=df['Stock'],
                    values=df['New Value'],
                    title="After Investment",
                    hole=0.3
                )])
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)

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
