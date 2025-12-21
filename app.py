import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Portfolio Allocation Calculator", page_icon="💰", layout="wide")

st.title("💰 Portfolio Allocation Calculator")
st.markdown("Calculate optimal investment amounts to rebalance your portfolio")

# Initialize session state for stocks
if 'stocks' not in st.session_state:
    st.session_state.stocks = [
        {"name": "Stock A", "current_value": 1000.0, "target_allocation": 30.0},
        {"name": "Stock B", "current_value": 1500.0, "target_allocation": 40.0},
        {"name": "Stock C", "current_value": 500.0, "target_allocation": 30.0},
    ]

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
                st.session_state.stocks.append({
                    "name": new_name,
                    "current_value": new_value,
                    "target_allocation": new_target
                })
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
    
    for idx, stock in enumerate(st.session_state.stocks):
        with st.container():
            cols = st.columns([3, 2, 2, 1])
            
            with cols[0]:
                stock['name'] = st.text_input(
                    "Name",
                    value=stock['name'],
                    key=f"name_{idx}",
                    label_visibility="collapsed"
                )
            
            with cols[1]:
                stock['current_value'] = st.number_input(
                    "Current Value",
                    min_value=0.0,
                    value=float(stock['current_value']),
                    step=100.0,
                    key=f"value_{idx}",
                    label_visibility="collapsed"
                )
            
            with cols[2]:
                stock['target_allocation'] = st.number_input(
                    "Target %",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(stock['target_allocation']),
                    step=1.0,
                    key=f"target_{idx}",
                    label_visibility="collapsed"
                )
            
            with cols[3]:
                if st.button("🗑️", key=f"remove_{idx}"):
                    stocks_to_remove.append(idx)
    
    # Remove stocks marked for deletion
    for idx in reversed(stocks_to_remove):
        st.session_state.stocks.pop(idx)
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
