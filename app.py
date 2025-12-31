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
        --primary-accent: #10B981; /* Emerald Green */
        --primary-hover: #059669;
        --bg-dark: #1E1E2E;
        --sidebar-light: #D1D5DB; /* Slightly Darker Grey */
        --card-dark: #2D2D3A;
        --text-light: #F8FAFC;
        --text-sidebar: #1F2937; /* Dark Charcoal */
    }

    .stApp {
        background-color: var(--bg-dark);
    }

    /* Sidebar Styling (Light Mode) */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-light);
        border-right: 1px solid rgba(0,0,0,0.05);
    }
    
    /* Input Labels in Sidebar (Dark Text) */
    [data-testid="stSidebar"] label p {
        color: var(--text-sidebar) !important;
        font-weight: 500 !important;
    }

    /* High-Visibility Sidebar Toggle (Show/Hide) */
    button[data-testid="stBaseButton-header"],
    button[data-testid="stBaseButton-headerNoPadding"],
    [data-testid="stSidebarCollapsedControl"] button {
        background-color: var(--primary-accent) !important;
        color: white !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4) !important;
    }
    
    button[data-testid="stBaseButton-header"]:hover,
    button[data-testid="stBaseButton-headerNoPadding"]:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background-color: var(--primary-hover) !important;
        transform: scale(1.1) !important;
    }

    button[data-testid="stBaseButton-header"] svg,
    button[data-testid="stBaseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: white !important;
        color: white !important;
    }
    
    /* Selectbox/Input values in sidebar */
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
        color: var(--text-sidebar) !important;
        background-color: white !important;
        border-radius: 8px !important;
    }

    /* Fix sidebar number input controls (+/-) visibility */
    [data-testid="stSidebar"] .stNumberInput div[data-baseweb="input"] {
        background-color: white !important;
    }
    
    [data-testid="stSidebar"] .stNumberInput button {
        background-color: #F3F4F6 !important;
        color: var(--text-sidebar) !important;
        border: none !important;
    }

    /* Fix selection text in sidebar inputs */
    /* Fix selection text in sidebar inputs - Remove contours globally (Aggressive) */
    /* Fix selection text in sidebar inputs - Remove contours globally (Aggressive) */
    [data-testid="stSidebar"] input,
    
    /* Target various containers to ensure background consistency */
    [data-testid="stSidebar"] div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-testid="stTextInput"] > div,
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    [data-testid="stSidebar"] div[data-baseweb="input"],
    [data-testid="stSidebar"] div[data-baseweb="base-input"] {
        background-color: white !important;
        border-radius: 8px !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        /* Force dark text and caret for visibility on white background */
        color: #31333F !important;
        caret-color: #31333F !important;
    }
    
    /* Ensure selection is visible within sidebar inputs */
    [data-testid="stSidebar"] input::selection {
        background-color: rgba(46, 204, 113, 0.4) !important; /* Primary accent fade */
        color: #31333F !important;
    }
    
    /* Target specific inner elements to ensure no internal borders */
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] .stTextInput input {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Remove borders from the buttons inside number inputs */
    [data-testid="stSidebar"] .stNumberInput button {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        border-left: 1px solid transparent !important; 
    }

    /* Expander Styling in Sidebar - Align with white inputs for maximum contrast */
    [data-testid="stSidebar"] details {
        border: 1px solid rgba(0,0,0,0.05) !important;
        border-radius: 12px !important;
        background-color: rgba(0,0,0,0.02) !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }
    
    [data-testid="stSidebar"] details summary {
        background-color: transparent !important;
        color: var(--text-sidebar) !important;
        padding: 5px 10px !important;
    }
    
    [data-testid="stSidebar"] details summary:hover {
        background-color: rgba(255,255,255,0.05) !important;
    }

    [data-testid="stSidebar"] details summary p {
        color: var(--text-sidebar) !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }

    /* Explicitly target expander chevron icons */
    [data-testid="stSidebar"] details summary svg,
    [data-testid="stSidebar"] details summary svg * {
        fill: var(--text-sidebar) !important;
        stroke: var(--text-sidebar) !important;
        color: var(--text-sidebar) !important;
    }

    /* Sidebar Checkbox Styling - Clean and minimal */
    [data-testid="stSidebar"] .stCheckbox,
    [data-testid="stSidebar"] .stCheckbox > label,
    [data-testid="stSidebar"] .stCheckbox label > div,
    [data-testid="stSidebar"] .stCheckbox label > div > div {
        background-color: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    [data-testid="stSidebar"] .stCheckbox > label {
        color: var(--text-sidebar) !important;
    }
    
    /* Checkbox Styling - Split Approach (Iteration 5) */
    
    /* 1. The Container (Label) - Ensure transparent */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] {
        background-color: transparent !important;
    }

    /* 2. The Visual Box (First Child) - White when unchecked */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child {
        background-color: white !important;
        border: 1px solid #9CA3AF !important;
        border-radius: 3px !important;
    }
    
    /* 3. The Text Label (Last Child) - Transparent */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:last-child {
        background-color: transparent !important;
        color: var(--text-sidebar) !important;
    }

    /* 4. CHECKED State for the Box Only */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child[aria-checked="true"],
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div:first-child {
        background-color: var(--primary-accent) !important;
        border-color: var(--primary-accent) !important;
    }
    
    /* Ensure inner checkmark is visible when checked */
    [data-testid="stSidebar"] [aria-checked="true"] svg {
        fill: white !important;
    }
    
    /* Ensure unchecked checkmark is invisible */
    [data-testid="stSidebar"] [aria-checked="false"] svg {
        fill: transparent !important;
    }
    
    /* Unchecked checkbox - make inner checkmark SVG invisible (only direct child) */
    [data-testid="stSidebar"] [data-baseweb="checkbox"]:not([aria-checked="true"]) > div > svg {
        fill: none !important;
        stroke: none !important;
        opacity: 0 !important;
    }
    
    /* Checked checkbox - emerald green with white checkmark */
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div {
        background-color: var(--primary-accent) !important;
        border-color: var(--primary-accent) !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div > svg {
        fill: white !important;
        opacity: 1 !important;
    }

    /* Help Icons (?) in sidebar - simple dark icons */
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"],
    [data-testid="stSidebar"] .stCheckbox [data-testid="stTooltipIcon"] {
        color: var(--text-sidebar) !important;
        opacity: 1 !important;
        visibility: visible !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: transparent !important;
        border: none !important;
        margin-left: 4px !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg,
    [data-testid="stSidebar"] .stCheckbox [data-testid="stTooltipIcon"] svg {
        fill: var(--text-sidebar) !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* Sidebar Dividers */
    [data-testid="stSidebar"] hr {
        border-color: rgba(0,0,0,0.05) !important;
    }

    /* Dataframe row separators - ensure borders are visible on all cells */
    [data-testid="stDataFrame"] td {
        border-bottom: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* Sidebar Headers & General Text - Universal Dark (Aggressive Targeting) */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] div,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] em,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h4,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h5,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h6,
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-sidebar) !important;
    }


    /* Sidebar Alerts/Info boxes */
    [data-testid="stSidebar"] div[data-testid="stNotification"] {
        background-color: rgba(0, 0, 0, 0.03) !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
    }
    
    /* Sidebar Alerts/Info boxes (Aggressive targeting for text visibility) */
    [data-testid="stSidebar"] div[data-testid="stNotification"] div,
    [data-testid="stSidebar"] div[data-testid="stNotification"] p,
    [data-testid="stSidebar"] div[data-testid="stNotification"] strong,
    [data-testid="stSidebar"] div[data-testid="stNotification"] span {
        color: var(--text-sidebar) !important;
    }

    /* EXPLICIT BUTTON TEXT PROTECTION IN SIDEBAR */
    [data-testid="stSidebar"] button p,
    [data-testid="stSidebar"] .stButton button p,
    [data-testid="stSidebar"] .stButton button span {
        color: white !important;
    }



    /* Target Streamlit's native containers for the "Card" look */
    /* This styles st.container(border=True) */
    [data-testid="stElementContainer"] > div:has(div.stVerticalBlockBorder) {
        background-color: var(--card-dark) !important;
        border-radius: 15px !important;
        padding: 24px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        margin-bottom: 20px !important;
    }

    /* KPI Metric Cards (Custom CSS for our HTML injection) */
    .kpi-card {
        background-color: var(--card-dark);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255,255,255,0.05);
        text-align: left;
        margin-bottom: 15px;
    }
    .kpi-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94A3B8;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .kpi-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: var(--text-light);
    }

    /* Primary Buttons (Emerald) */
    div.stButton > button:first-child {
        background-color: var(--primary-accent);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    div.stButton > button:first-child:hover {
        background-color: var(--primary-hover);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    
        /* Danger Buttons (for Remove) - Centered Emoji */
    div.stButton button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    div.stButton button p {
        width: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Specifically for remove buttons (red cross) */
    div[data-testid="stButton"] button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    div[data-testid="stButton"] button p {
        width: auto !important;
        margin: 0 !important;
        flex: 1 !important;
        text-align: center !important;
    }


    div[data-testid="stButton"]:has(button:contains("❌")) button:hover,
    .danger-btn div.stButton > button:first-child:hover {
        background-color: #FCA5A5 !important;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2) !important;
    }

    /* Target specific inputs in the management table for better alignment */
    [data-testid="stVerticalBlock"] .stNumberInput input,
    [data-testid="stVerticalBlock"] .stTextInput input {
        padding-top: 5px !important;
        padding-bottom: 5px !important;
        height: 38px !important;
    }

    /* Main App Content - Universal White for Dark Mode (Robust Targeting) */
    [data-testid="stAppViewContainer"] h1, 
    [data-testid="stAppViewContainer"] h2, 
    [data-testid="stAppViewContainer"] h3, 
    [data-testid="stAppViewContainer"] h4, 
    [data-testid="stAppViewContainer"] h5, 
    [data-testid="stAppViewContainer"] h6,
    [data-testid="stAppViewContainer"] p, 
    [data-testid="stAppViewContainer"] label, 
    [data-testid="stAppViewContainer"] span, 
    [data-testid="stAppViewContainer"] .stMarkdown {
        color: var(--text-light) !important;
    }

    /* Custom Headers for Main Content */
    h1, h2, h3 {
        color: var(--text-light) !important;
        font-weight: 800;
    }

    /* Hide standard Streamlit extras but keep the header for the sidebar toggle */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stHeader"] > div {
        visibility: visible !important;
    }
    /* Specifically hide the deploy button and other header junk */
    [data-testid="stHeader"] button[data-testid="stBaseButton-secondary"],
    [data-testid="stHeader"] div[data-testid="stStatusWidget"] {
        display: none !important;
    }
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
if 'show_save_success' not in st.session_state:
    st.session_state.show_save_success = False

def clear_recommendations():
    st.session_state.show_recommendations = False
    st.session_state.show_save_success = False
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
            
            required_columns = [
                'username', 'stock_name', 'current_value', 'target_allocation', 
                'portfolio_name', 'tolerance', 'portfolio_monthly_invest', 
                'portfolio_use_indicators', 'portfolio_buffett_index'
            ]
            
            if raw_data.empty:
                raw_data = pd.DataFrame(columns=required_columns)
            else:
                for col in required_columns:
                    if col not in raw_data.columns:
                        if col == 'portfolio_monthly_invest': raw_data[col] = 1000.0
                        elif col == 'portfolio_use_indicators': raw_data[col] = False
                        elif col == 'portfolio_buffett_index': raw_data[col] = 195.0
                        elif col in ['current_value', 'target_allocation', 'tolerance']: raw_data[col] = 0.0
                        else: raw_data[col] = ''
                        
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
            with st.expander("➕ Create New Portfolio"):
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
    
    # Order by Target % (Descending)
    if not user_portfolio_df.empty:
        user_portfolio_df = user_portfolio_df.sort_values(by='target_allocation', ascending=False)
    
    current_stocks = []
    for _, row in user_portfolio_df.iterrows():
        current_stocks.append({
            "name": row['stock_name'],
            "current_value": row['current_value'],
            "target_allocation": row['target_allocation'],
            "tolerance": row.get('tolerance', 0.0)
        })
    
    # We store the original values for change detection
    st.session_state.stocks = current_stocks

    # Pre-populate session state keys for widgets if they don't exist
    if selected_portfolio:
        # Load portfolio-level config from the first row of user_portfolio_df
        if not user_portfolio_df.empty:
            first_row = user_portfolio_df.iloc[0]
            if f"{selected_portfolio}_monthly_invest" not in st.session_state:
                st.session_state[f"{selected_portfolio}_monthly_invest"] = float(first_row.get('portfolio_monthly_invest', 1000.0))
            if f"{selected_portfolio}_use_indicators" not in st.session_state:
                st.session_state[f"{selected_portfolio}_use_indicators"] = bool(first_row.get('portfolio_use_indicators', False))
            if f"{selected_portfolio}_buffett_index" not in st.session_state:
                st.session_state[f"{selected_portfolio}_buffett_index"] = float(first_row.get('portfolio_buffett_index', 195.0))

        for idx, stock in enumerate(current_stocks):
            key_prefix = f"{selected_portfolio}_{idx}"
            if f"{key_prefix}_name" not in st.session_state:
                st.session_state[f"{key_prefix}_name"] = stock['name']
            if f"{key_prefix}_value" not in st.session_state:
                st.session_state[f"{key_prefix}_value"] = float(stock['current_value'])
            if f"{key_prefix}_target" not in st.session_state:
                st.session_state[f"{key_prefix}_target"] = float(stock['target_allocation'])
            if f"{key_prefix}_tolerance" not in st.session_state:
                st.session_state[f"{key_prefix}_tolerance"] = float(stock.get('tolerance', 0.0))

    # Sidebar utilities (Configuration and Indicators)
    with st.sidebar:
        if selected_portfolio:
            # 2. Configuration Section
            with st.expander("⚙️ Configuration", expanded=False):
                monthly_investment_key = f"{selected_portfolio}_monthly_invest"
                monthly_investment = st.number_input(
                    "Monthly Investment Amount (€)",
                    min_value=0.0,
                    key=monthly_investment_key,
                    step=100.0,
                    help="Amount you want to invest this month",
                    on_change=clear_recommendations
                )
                
                # Market Indicators
                st.markdown("### Market Indicators")
                
                # Track state transitions for reverting to manual targets
                if 'prev_indicators_state' not in st.session_state:
                    st.session_state.prev_indicators_state = False
                    
                use_indicators_key = f"{selected_portfolio}_use_indicators"
                use_market_indicators = st.checkbox(
                    "Use Market Indicators", 
                    key=use_indicators_key,
                    help="Enable rebalancing rules based on Buffett Indicator",
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
                    buffett_index_key = f"{selected_portfolio}_buffett_index"
                    buffett_index = st.number_input(
                        "Buffett Indicator (%)", 
                        key=buffett_index_key,
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
                new_tolerance = st.number_input("Rebalancing Tolerance (%)", min_value=0.0, max_value=20.0, value=0.0, key="new_tolerance", help="Don't rebalance if drift is less/more than this %")
                
                if st.button("Add Stock"):
                    if new_name:
                        # Get current portfolio-level config
                        p_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                        p_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                        p_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)

                        new_row = pd.DataFrame([{
                            "username": username,
                            "stock_name": new_name,
                            "current_value": new_value,
                            "target_allocation": new_target,
                            "tolerance": new_tolerance,
                            "portfolio_name": selected_portfolio,
                            "portfolio_monthly_invest": p_invest,
                            "portfolio_use_indicators": p_use_ind,
                            "portfolio_buffett_index": p_buffett
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
                    h_cols = st.columns([3, 2, 2, 2, 1])
                    h_cols[0].markdown("**Ticker**")
                    h_cols[1].markdown("**Value (€)**")
                    h_cols[2].markdown("**Target %**")
                    h_cols[3].markdown("**Tolerance %**")

                    for idx, stock in enumerate(st.session_state.stocks):
                        if stock['name'] == "__PLACEHOLDER__": continue
                        key_prefix = f"{selected_portfolio}_{idx}"
                        r_cols = st.columns([3, 2, 2, 2, 1], vertical_alignment="center")
                        with r_cols[0]:
                            st.text_input("Name", key=f"{key_prefix}_name", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[1]:
                            st.number_input("Value", min_value=0.0, step=100.0, key=f"{key_prefix}_value", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[2]:
                            st.number_input("Target", min_value=0.0, max_value=100.0, step=1.0, key=f"{key_prefix}_target", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[3]:
                            st.number_input("Tolerance", min_value=0.0, max_value=20.0, step=0.1, key=f"{key_prefix}_tolerance", label_visibility="collapsed", on_change=clear_recommendations)
                        with r_cols[4]:
                            if st.button("❌", key=f"{key_prefix}_remove"):
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
                        # Always update configuration for the selected portfolio across all its rows
                        portfolio_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                        portfolio_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                        portfolio_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)

                        # Update configuration in 'data' for all rows matching this portfolio
                        # This ensures the configuration is "broadcasted" to all rows
                        mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        data.loc[mask, 'portfolio_monthly_invest'] = portfolio_invest
                        data.loc[mask, 'portfolio_use_indicators'] = portfolio_use_ind
                        data.loc[mask, 'portfolio_buffett_index'] = portfolio_buffett

                        # Check for stock-level changes
                        for idx, stock in enumerate(st.session_state.stocks):
                            key_prefix = f"{selected_portfolio}_{idx}"
                            new_name = st.session_state.get(f"{key_prefix}_name")
                            new_val = st.session_state.get(f"{key_prefix}_value")
                            new_target = st.session_state.get(f"{key_prefix}_target")
                            new_tolerance = st.session_state.get(f"{key_prefix}_tolerance")
                            orig_row = user_portfolio_df.iloc[idx]

                            if (new_name != orig_row['stock_name'] or 
                                abs(new_val - orig_row['current_value']) > 0.01 or 
                                abs(new_target - orig_row['target_allocation']) > 0.01 or
                                abs(new_tolerance - orig_row.get('tolerance', 0.0)) > 0.01):
                                filtered_idx = user_portfolio_df.index[idx]
                                data.at[filtered_idx, 'stock_name'] = new_name
                                data.at[filtered_idx, 'current_value'] = new_val
                                data.at[filtered_idx, 'target_allocation'] = new_target
                                data.at[filtered_idx, 'tolerance'] = new_tolerance
                                any_content_changes = True
                        
                        # Configuration changes also count as changes
                        # We compare against the first row of user_portfolio_df
                        if not user_portfolio_df.empty:
                            fr = user_portfolio_df.iloc[0]
                            if (abs(portfolio_invest - fr.get('portfolio_monthly_invest', 1000.0)) > 0.1 or
                                portfolio_use_ind != fr.get('portfolio_use_indicators', False) or
                                abs(portfolio_buffett - fr.get('portfolio_buffett_index', 195.0)) > 0.1):
                                any_content_changes = True

                        if any_content_changes or st.session_state.has_unsaved_changes:
                            st.session_state.master_data = data
                            conn.update(worksheet="Portfolios", data=data)
                            st.session_state.has_unsaved_changes = False
                            st.session_state.show_save_success = True
                            st.rerun()
                    
                    if st.session_state.get('show_save_success'):
                        st.success("All changes saved successfully!")

        with col_side:
            with st.container(border=True):
                st.subheader("🎯 Action Center")
                if st.button("🧮 Calculate Allocation", width="stretch"):
                    if abs(sum(s['target_allocation'] for s in live_stocks) - 100.0) > 0.01:
                        st.error("Ratios must sum to 100%")
                    else:
                        total_current = sum(s['current_value'] for s in live_stocks)
                        new_total_theoretical = total_current + monthly_investment
                        
                        eligible_stocks = []
                        for stock in live_stocks:
                            current_pct = (stock['current_value'] / total_current * 100) if total_current > 0 else 0
                            target_pct = stock['target_allocation']
                            tolerance = stock.get('tolerance', 0.0)
                            
                            # Tolerance Rule: Only invest if current % is below (target % - tolerance %)
                            # OR if the stock is brand new (current value is 0)
                            if stock['current_value'] == 0 or current_pct < (target_pct - tolerance):
                                eligible_stocks.append(stock)
                        
                        if not eligible_stocks:
                            st.warning("All stocks are within their tolerance bands! No rebalancing needed.")
                            # Fallback: Treat all as eligible if they all passed the check but we still want to invest?
                            # No, let's respect the user's tolerance. If they forced it, we could have a toggle.
                            # For now, let's just use live_stocks if everything is skipped to avoid "0 results".
                            eligible_stocks = live_stocks 

                        stock_gaps = []
                        # Recalculate gaps only for eligible stocks (or all if fallback triggered)
                        # We use the full new_total_theoretical to find the 'true' gap
                        for stock in eligible_stocks:
                            target_val = new_total_theoretical * (stock['target_allocation'] / 100.0)
                            gap = target_val - stock['current_value']
                            stock_gaps.append({"Stock": stock['name'], "Target Value": target_val, "Gap": gap, "stock": stock})
                        
                        sorted_gaps = sorted(stock_gaps, key=lambda x: x['Gap'], reverse=True)
                        remaining_investment = float(monthly_investment)
                        
                        temp_allocs = []
                        for item in sorted_gaps:
                            ideal_invest = max(0.0, min(item['Gap'], remaining_investment))
                            import math
                            floored_invest = float(math.floor(ideal_invest))
                            remaining_investment -= floored_invest
                            temp_allocs.append({"item": item, "invest": floored_invest})
                        
                        if temp_allocs:
                            temp_allocs[0]['invest'] += remaining_investment
                            remaining_investment = 0.0 
                        
                        allocations = []
                        new_total_actual = float(total_current + monthly_investment)
                        for row in temp_allocs:
                            item = row['item']
                            final_invest = row['invest']
                            stock = item['stock']
                            new_val = stock['current_value'] + final_invest
                            allocations.append({
                                "Stock": item['Stock'], 
                                "Current Value": stock['current_value'], 
                                "Current %": (stock['current_value'] / total_current * 100) if total_current > 0 else 0, 
                                "Target %": stock['target_allocation'], 
                                "Target Value": item['Target Value'],
                                "Investment": final_invest, 
                                "New Value": new_val, 
                                "New %": (new_val / new_total_actual * 100) if new_total_actual > 0 else 0
                            })
                        
                        st.session_state.last_calculation = {"df": pd.DataFrame(allocations), "monthly_investment": monthly_investment, "remaining": remaining_investment}
                        st.session_state.show_recommendations = True
                
                if st.session_state.show_recommendations:
                    # st.divider()
                    calc = st.session_state.last_calculation
                    if calc['remaining'] > 0.01:
                        st.warning(f"Note: €{calc['remaining']:.2f} could not be allocated.")
                    st.success("Allocation Calculated!")

        # --- Bottom Row: Results & Visualization ---
        if st.session_state.show_recommendations:
            with st.container(border=True):
                st.subheader("📋 Investment Recommendations")
                df = st.session_state.last_calculation['df']
                # Highlight and style the 'Investment' column
                styled_df = df.style.format(precision=2).set_properties(
                    subset=['Investment'], 
                    **{'background-color': '#24A16F', 'color': '#065F46', 'font-weight': '700', 
                       'border-bottom': '1px solid #065F46'}
                )
                st.table(styled_df)
                
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
                    fig1.update_layout(
                        title_text="Current Allocation", 
                        title_font=dict(size=24), 
                        legend=dict(font=dict(size=18)),
                        font=dict(size=16), # Global font size for labels
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                with chart_col2:
                    fig2 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['New Value'], hole=0.3, marker=dict(colors=dashboard_colors))])
                    fig2.update_layout(
                        title_text="After Investment", 
                        title_font=dict(size=24), 
                        legend=dict(font=dict(size=18)),
                        font=dict(size=16), # Global font size for labels
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig2, use_container_width=True)

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
