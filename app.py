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

st.set_page_config(page_title="Portfolio Master", page_icon="🚀", layout="wide")

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
if 'undo_buffer' not in st.session_state:
    st.session_state.undo_buffer = []
if 'show_undo' not in st.session_state:
    st.session_state.show_undo = False
if 'editor_key' not in st.session_state:
    st.session_state.editor_key = 0

def clear_recommendations():
    st.session_state.show_recommendations = False
    st.session_state.show_save_success = False
    st.session_state.last_calculation = None

def calculate_kids_targets(birth_date_str):
    if not birth_date_str or not isinstance(birth_date_str, str):
        return None
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        if age <= 13:
            return {"VWCE.DE": 100.0, "VAGF.DE": 0.0}
        elif age == 14:
            return {"VWCE.DE": 90.0, "VAGF.DE": 10.0}
        elif age == 15:
            return {"VWCE.DE": 85.0, "VAGF.DE": 15.0}
        elif age == 16:
            return {"VWCE.DE": 80.0, "VAGF.DE": 20.0}
        elif age == 17:
            return {"VWCE.DE": 70.0, "VAGF.DE": 30.0}
        elif age >= 18:
            return {"VWCE.DE": 60.0, "VAGF.DE": 40.0}
    except Exception:
        return None
    return None

def reset_portfolio_state():
    clear_recommendations()
    if 'portfolio_selector' in st.session_state:
        selected = st.session_state.portfolio_selector
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"{selected}_")]
        for k in keys_to_clear:
            del st.session_state[k]
    # Force re-sync of stocks state on next run
    if 'last_selected_portfolio' in st.session_state:
        del st.session_state.last_selected_portfolio

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
    st.title("🚀 Portfolio Master: Allocation & Analytics")
    st.markdown("Optimization, Dividend Tracking, and Portfolio Analytics")

    # Initialize dynamic footer message
    if 'footer_msg' not in st.session_state:
        st.session_state.footer_msg = "<b>Smart Rebalancing:</b> Maintain your risk profile with disciplined allocation."
    
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
                'portfolio_name', 'tolerance', 'expense_ratio', 'portfolio_monthly_invest', 
                'portfolio_use_indicators', 'portfolio_buffett_index',
                'stock_full_name', 'sector', 'industry', 'country', 'currency', 
                'quantity', 'average_price', 'dividend_yield', 'portfolio_type',
                'portfolio_birth_date'
            ]
            
            if raw_data.empty:
                raw_data = pd.DataFrame(columns=required_columns)
            else:
                for col in required_columns:
                    if col not in raw_data.columns:
                        if col == 'portfolio_monthly_invest': raw_data[col] = 1000.0
                        elif col == 'portfolio_use_indicators': raw_data[col] = False
                        elif col == 'portfolio_buffett_index': raw_data[col] = 195.0
                        elif col == 'portfolio_type': raw_data[col] = 'Other'
                        elif col == 'portfolio_birth_date': raw_data[col] = ''
                        elif col in ['current_value', 'target_allocation', 'tolerance', 'expense_ratio', 'quantity', 'average_price', 'dividend_yield']: raw_data[col] = 0.0
                        else: raw_data[col] = ''
                        
                raw_data = raw_data.astype({
                    'username': 'str',
                    'stock_name': 'str', 
                    'current_value': 'float',
                    'target_allocation': 'float',
                    'expense_ratio': 'float',
                    'portfolio_name': 'str'
                })
                raw_data['portfolio_name'] = raw_data['portfolio_name'].fillna('Default')
                raw_data['username'] = raw_data['username'].fillna('unknown') 

            st.session_state.master_data = raw_data

            # Load Dividends Data
            if 'dividends' not in st.session_state:
                try:
                    div_data = conn.read(worksheet="Dividends", ttl=0)
                    if div_data is None or div_data.empty:
                        div_data = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])
                    # Ensure columns exist
                    for col in ['date', 'ticker', 'amount', 'portfolio_name', 'username']:
                        if col not in div_data.columns:
                            div_data[col] = '' if col in ['date', 'ticker', 'portfolio_name', 'username'] else 0.0
                    st.session_state.dividends = div_data
                except Exception:
                     # Worksheet likely doesn't exist yet
                    st.session_state.dividends = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])

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
                new_portfolio_input = st.text_input("Name", placeholder="e.g., Retirement", key="new_p_name")
                new_portfolio_type = st.selectbox("Type", options=["Stocks", "Dividends", "Kids", "Other"], index=3, key="new_p_type")
                if st.button("Create"):
                    if new_portfolio_input and new_portfolio_input not in existing_portfolios:
                        # Create a placeholder row to persist the portfolio name
                        new_row = pd.DataFrame([{
                            "username": username,
                            "portfolio_name": new_portfolio_input,
                            "stock_name": "__PLACEHOLDER__",
                            "current_value": 0.0,
                            "target_allocation": 0.0,
                            "portfolio_type": new_portfolio_type,
                            "portfolio_birth_date": ""
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
                with st.expander(f"⚙️ Portfolio Settings"):
                    # Get current type for default
                    current_type = user_all_data[user_all_data['portfolio_name'] == selected_portfolio]['portfolio_type'].iloc[0] if not user_all_data[user_all_data['portfolio_name'] == selected_portfolio].empty else "Other"
                    type_options = ["Stocks", "Dividends", "Kids", "Other"]
                    type_index = type_options.index(current_type) if current_type in type_options else 3

                    new_name_input = st.text_input("Rename Portfolio", value=selected_portfolio, placeholder="e.g., Retirement 2026")
                    new_type_input = st.selectbox("Portfolio Type", options=type_options, index=type_index)
                    
                    if st.button("Save Settings"):
                        # Check if name changed and if new name already exists
                        name_changed = new_name_input != selected_portfolio
                        type_changed = new_type_input != current_type

                        if name_changed and new_name_input in existing_portfolios:
                            st.error("A portfolio with this name already exists.")
                        elif name_changed or type_changed:
                            # Update all rows in master data
                            mask = (st.session_state.master_data['username'] == username) & \
                                   (st.session_state.master_data['portfolio_name'] == selected_portfolio)
                            
                            if name_changed:
                                st.session_state.master_data.loc[mask, 'portfolio_name'] = new_name_input
                                success_msg = f"Renamed to '{new_name_input}'"
                                final_name = new_name_input
                            else:
                                final_name = selected_portfolio
                                success_msg = "Settings updated"

                            if type_changed:
                                st.session_state.master_data.loc[mask, 'portfolio_type'] = new_type_input
                                success_msg += " and type updated" if name_changed else "Type updated"

                            conn.update(worksheet="Portfolios", data=st.session_state.master_data)
                            
                            st.session_state.new_portfolio_created = final_name
                            st.session_state.has_unsaved_changes = False # Just synced
                            reset_portfolio_state()
                            st.success(f"{success_msg}!")
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
    p_type = "Other"
    if selected_portfolio:
        p_rows = user_all_data[user_all_data['portfolio_name'] == selected_portfolio]
        if not p_rows.empty:
            p_type = p_rows['portfolio_type'].iloc[0]

    user_portfolio_df = user_all_data[user_all_data['portfolio_name'] == selected_portfolio] if selected_portfolio else pd.DataFrame()
    user_portfolio_df = user_portfolio_df[user_portfolio_df['stock_name'] != "__PLACEHOLDER__"] if not user_portfolio_df.empty else pd.DataFrame()
    
    # 2. Main Page Header & State Management Logic (Sync with DB) for consistent UI
    if not user_portfolio_df.empty:
        user_portfolio_df = user_portfolio_df.sort_values(by='target_allocation', ascending=False)
    
    # Initialize session state for stocks ONLY if portfolio changes or it's first run
    if st.session_state.get('last_selected_portfolio') != selected_portfolio:
        current_stocks = []
        for _, row in user_portfolio_df.iterrows():
            current_stocks.append({
                "name": row['stock_name'],
                "current_value": row['current_value'],
                "target_allocation": row['target_allocation'],
                "tolerance": row.get('tolerance', 0.0),
                "expense_ratio": row.get('expense_ratio', 0.0),
                "full_name": row.get('stock_full_name', ''),
                "sector": row.get('sector', ''),
                "industry": row.get('industry', ''),
                "country": row.get('country', ''),
                "currency": row.get('currency', ''),
                "quantity": float(row.get('quantity', 0.0)),
                "average_price": float(row.get('average_price', 0.0)),
                "dividend_yield": float(row.get('dividend_yield', 0.0))
            })
        st.session_state.stocks = current_stocks
        st.session_state.last_selected_portfolio = selected_portfolio

        # Pre-populate session state keys for widgets if they don't exist
        if selected_portfolio:
            # Load portfolio-level config from the first row of user_portfolio_df
            if not user_portfolio_df.empty:
                first_row = user_portfolio_df.iloc[0]
                # Note: We use fixed keys for portfolio-level settings
                st.session_state[f"{selected_portfolio}_monthly_invest"] = float(first_row.get('portfolio_monthly_invest', 1000.0))
                st.session_state[f"{selected_portfolio}_use_indicators"] = bool(first_row.get('portfolio_use_indicators', False))
                st.session_state[f"{selected_portfolio}_buffett_index"] = float(first_row.get('portfolio_buffett_index', 195.0))
                st.session_state[f"{selected_portfolio}_birth_date"] = first_row.get('portfolio_birth_date', '')
                
                # Auto-update targets for Kids portfolios on load (child got older)
                if p_type == "Kids" and st.session_state[f"{selected_portfolio}_birth_date"]:
                    kids_targets = calculate_kids_targets(st.session_state[f"{selected_portfolio}_birth_date"])
                    if kids_targets:
                        for ticker, target in kids_targets.items():
                            for stock in st.session_state.stocks:
                                if stock['name'] == ticker:
                                    stock['target_allocation'] = target
                                    break

            for idx, stock in enumerate(st.session_state.stocks):
                key_prefix = f"{selected_portfolio}_{idx}"
                st.session_state[f"{key_prefix}_name"] = stock['name']
                st.session_state[f"{key_prefix}_value"] = float(stock['current_value'])
                st.session_state[f"{key_prefix}_target"] = float(stock['target_allocation'])
                st.session_state[f"{key_prefix}_tolerance"] = float(stock.get('tolerance', 0.0))

    # Sidebar utilities (Configuration and Indicators)
    with st.sidebar:
        if selected_portfolio:
            # 2. Configuration Section
            if p_type in ["Dividends", "Kids", "Other"]:
                # Default expander behavior: auto-expand for 'Kids' to set birth date, others remain collapsed
                with st.expander("⚙️ Configuration", expanded=(p_type == "Kids")):
                    if p_type == "Kids":
                        birth_date_key = f"{selected_portfolio}_birth_date"
                        current_birth_date = st.session_state.get(birth_date_key, '')
                        
                        try:
                            # Robust check for string type to avoid numpy.float64 (NaN) crashes
                            if isinstance(current_birth_date, str) and current_birth_date:
                                default_date = datetime.strptime(current_birth_date, "%Y-%m-%d").date()
                            else:
                                default_date = datetime.today().date()
                        except ValueError:
                            default_date = datetime.today().date()
                            
                        birth_date_input = st.date_input(
                            "Child's Birth Date",
                            value=default_date,
                            min_value=datetime(1900, 1, 1).date(),
                            max_value=datetime(2100, 1, 1).date(),
                            key=f"{birth_date_key}_input",
                            on_change=clear_recommendations
                        )
                        
                        if str(birth_date_input) != current_birth_date:
                            st.session_state[birth_date_key] = str(birth_date_input)
                            st.session_state.has_unsaved_changes = True
                            
                            # Auto-calculate age-based targets
                            kids_targets = calculate_kids_targets(str(birth_date_input))
                            if kids_targets:
                                existing_tickers = {s['name'] for s in st.session_state.stocks}
                                for ticker, target in kids_targets.items():
                                    if ticker in existing_tickers:
                                        for i, stock in enumerate(st.session_state.stocks):
                                            if stock['name'] == ticker:
                                                st.session_state.stocks[i]['target_allocation'] = target
                                                st.session_state[f"{selected_portfolio}_{i}_target"] = target
                                                break
                                    elif ticker in ["VWCE.DE", "VAGF.DE"]:
                                        # Auto-inject core tickers if they don't exist in the portfolio yet
                                        st.session_state.stocks.append({
                                            "name": ticker,
                                            "current_value": 0.0,
                                            "target_allocation": target,
                                            "tolerance": 2.0,
                                            "expense_ratio": 0.0,
                                            "full_name": ticker,
                                            "sector": "", "industry": "", "country": "", "currency": "EUR", "quantity": 0.0, "average_price": 0.0, "dividend_yield": 0.0
                                        })
                                st.toast("👶 Age-based targets updated!", icon="✅")
                                st.rerun()

                    monthly_investment_key = f"{selected_portfolio}_monthly_invest"
                    
                    monthly_investment = st.number_input(
                        "Monthly Investment Amount (€)",
                        min_value=0.0,
                        value=st.session_state.get(monthly_investment_key, 1000.0),
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
            else:
                # Still need defaults for variables used later even if hidden
                monthly_investment = 0.0
                use_market_indicators = False
                buffett_index = 195.0
            
            # 3. Add Stock Section
            with st.expander("🛠️ Stock Management", expanded=False):
                # Using centralized p_type defined earlier

                st.markdown("➕ **Add New Stock**")
                new_name = st.text_input("Ticker")
                value_label = "Value (€)" if p_type == "Stocks" else "Current Value (€)"
                new_value = st.number_input(value_label, min_value=0.0, value=0.0, key="new_value")
                
                # Initialize defaults for conditional fields
                new_target = 0.0
                new_tolerance = 2.0
                new_ter = 0.0
                new_full_name = ""
                new_sector = ""
                new_industry = ""
                new_country = ""
                new_currency = ""
                new_qty = 0.0
                new_avg_price = 0.0
                new_div_yield = 0.0

                if p_type == "Stocks":
                    new_qty = st.number_input("Quantity", min_value=0.0, value=0.0, step=0.01, key="new_qty")
                    new_avg_price = st.number_input("Average Price", min_value=0.0, value=0.0, step=0.01, key="new_avg")
                    new_div_yield = st.number_input("Div. Yield (%)", min_value=0.0, value=0.0, step=0.01, key="new_dy")
                    
                    new_full_name = st.text_input("Company Name", key="new_full_name")
                    m_col1, m_col2 = st.columns(2)
                    with m_col1:
                        new_sector = st.text_input("Sector", key="new_sector")
                        new_industry = st.text_input("Industry", key="new_industry")
                    with m_col2:
                        new_country = st.text_input("Country", key="new_country")
                        new_currency = st.text_input("Currency", key="new_currency")
                else:
                    new_target = st.number_input("Target Allocation (%)", min_value=0.0, max_value=100.0, value=0.0, key="new_target")
                    new_tolerance = st.number_input("Rebalancing Tolerance (%)", min_value=0.0, max_value=20.0, value=2.0, key="new_tolerance", help="Don't rebalance if drift is less/more than this %")
                    new_ter = st.number_input("Expense Ratio (TER %)", min_value=0.0, max_value=5.0, value=0.0, step=0.01, key="new_ter")
                
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
                            "expense_ratio": new_ter,
                            "portfolio_name": selected_portfolio,
                            "portfolio_monthly_invest": p_invest,
                            "portfolio_use_indicators": p_use_ind,
                            "portfolio_buffett_index": p_buffett,
                            "stock_full_name": new_full_name,
                            "sector": new_sector,
                            "industry": new_industry,
                            "country": new_country,
                            "currency": new_currency,
                            "quantity": new_qty,
                            "average_price": new_avg_price,
                            "dividend_yield": new_div_yield,
                            "portfolio_type": p_type,
                            "portfolio_birth_date": st.session_state.get(f"{selected_portfolio}_birth_date", "")
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
        # Synchronize "live" values for calculations (Summary/Recommendations) 
        # Source of truth is now exclusively st.session_state.stocks (synced with Editor)
        live_stocks = st.session_state.stocks.copy() if 'stocks' in st.session_state else []

        # --- Top Row: KPI Cards ---
        total_current = sum(s['current_value'] for s in live_stocks)
        total_target = sum(s['target_allocation'] for s in live_stocks)
        num_stocks = len(live_stocks)
        
        # Dashboard Header
        st.markdown(f"## 📊 {selected_portfolio} Dashboard")
        
        # Calculate Weighted TER for KPI
        total_ter_sum = 0.0
        for s in live_stocks:
            try:
                val = float(s.get('current_value', 0.0))
                ter = float(s.get('expense_ratio', 0.0))
                total_ter_sum += (val * ter)
            except (ValueError, TypeError):
                continue
                
        weighted_ter = (total_ter_sum / total_current) if total_current > 0 else 0.0

        if p_type == "Stocks":
            # Calculate Unique Sectors
            unique_sectors = set(s.get('sector', '') for s in live_stocks if s.get('sector', ''))
            num_sectors = len(unique_sectors)

            kpi_cols = st.columns(3)
            with kpi_cols[0]: render_kpi_card("Total Value", f"€{total_current:,.2f}")
            with kpi_cols[1]: render_kpi_card("Stocks Count", f"{num_stocks}")
            with kpi_cols[2]: render_kpi_card("Sectors", f"{num_sectors}")
        else:
            kpi_cols = st.columns(5)
            with kpi_cols[0]: render_kpi_card("Total Value", f"€{total_current:,.2f}")
            with kpi_cols[1]: render_kpi_card("Stocks Count", f"{num_stocks}")
            with kpi_cols[2]: render_kpi_card("Target Spread", f"{total_target:.1f}%")
            with kpi_cols[3]: render_kpi_card("Weighted TER", f"{weighted_ter:.2f}%")
            with kpi_cols[4]: render_kpi_card("Monthly Budget", f"€{monthly_investment:,.2f}")
        
        if p_type != "Stocks" and abs(total_target - 100.0) > 0.01:
            st.warning("⚠️ Your target allocations do not sum to 100%. Please adjust them in Portfolio Management.")

        # --- Tab Routing Logic ---
        
        tab_list = []
        if p_type == "Stocks":
            tab_list = ["📈 Portfolio Details"]
        elif p_type == "Dividends":
            tab_list = ["📊 Manage Portfolio", "💰 Dividend Tracker"]
        else: # Other
            tab_list = ["📊 Manage Portfolio"]
            
        tabs = st.tabs(tab_list)
        
        # Link tab objects to labels for easier conditional rendering
        tab_map = {label: tabs[i] for i, label in enumerate(tab_list)}

        if "📊 Manage Portfolio" in tab_map:
            with tab_map["📊 Manage Portfolio"]:
                st.session_state.footer_msg = "<b>Smart Rebalancing:</b> Maintain your risk profile with disciplined allocation."
                col_main, col_side = st.columns([2, 1])
        
                with col_main:
                    with st.container(border=True):
                        st.subheader("📝 Portfolio Management")
                        
                        # Prepare data for Editor
                        current_stocks_df = pd.DataFrame(st.session_state.stocks)
                        if not current_stocks_df.empty:
                            # Freeze Ticker by setting as Index
                            current_stocks_df.set_index("name", inplace=True)
                            
                            # Slice to only include core rebalancing columns for this tab
                            core_cols = ["current_value", "target_allocation", "tolerance", "expense_ratio"]
                            available_core = [c for c in core_cols if c in current_stocks_df.columns]
                            current_stocks_df = current_stocks_df[available_core]
                        else:
                            current_stocks_df = pd.DataFrame(columns=["current_value", "target_allocation", "tolerance", "expense_ratio"])
                            current_stocks_df.index.name = "name"
                        
                        # Configuration for Data Editor
                        column_config = {
                            "name": st.column_config.TextColumn("Ticker", required=True),
                            "current_value": st.column_config.NumberColumn("Value (€)", min_value=0.0, step=100.0, format="%.2f"),
                            "target_allocation": st.column_config.NumberColumn("Target %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f%%", disabled=(p_type == "Kids")),
                            "tolerance": st.column_config.NumberColumn("Tolerance %", min_value=0.0, max_value=20.0, step=0.1, format="%.1f%%"),
                            "expense_ratio": st.column_config.NumberColumn("TER %", min_value=0.0, max_value=5.0, step=0.01, format="%.2f%%")
                        }
                        
                        edited_df = st.data_editor(
                            current_stocks_df,
                            column_config=column_config,
                            num_rows="dynamic",
                            use_container_width=True,
                            key=f"portfolio_editor_{st.session_state.editor_key}",
                            on_change=clear_recommendations
                        )
                        
                        # Sync Editor Changes to Session State immediately for "Live Calc"
                        # This ensures charts and calculations use the latest typed values even before saving
                        if not edited_df.equals(current_stocks_df):
                            # DETECT DELETIONS
                            # Must reset index to get 'name' back into the columns for to_dict('records')
                            updated_stocks = edited_df.reset_index().to_dict('records')
                            old_stocks = current_stocks_df.reset_index().to_dict('records')
        
                            if len(updated_stocks) < len(old_stocks):
                                # Row(s) were deleted
                                # Identify exactly which ones are missing based on 'name' (assuming unique names)
                                updated_names = {row['name'] for row in updated_stocks}
                                deleted_items = [row for row in old_stocks if row['name'] not in updated_names]
                                
                                st.session_state.undo_buffer = deleted_items
                                st.session_state.show_undo = True
                                st.toast(f"Deleted {len(deleted_items)} stock(s)", icon="🗑️")
                            elif len(updated_stocks) >= len(old_stocks):
                                # Add or Edit action -> Clear undo history to avoid confusion
                                st.session_state.show_undo = False
                                st.session_state.undo_buffer = []
        
                            st.session_state.stocks = updated_stocks
                            st.session_state.has_unsaved_changes = True
                            # Aggressive sync: Rerun ensures Dashboard KPIs and other blocks see the new state immediately
                            st.rerun()
        
                        # UNDO BUTTON
                        if st.session_state.show_undo:
                            if st.button("↩️ Undo Delete"):
                                if st.session_state.undo_buffer:
                                    # Restore deleted items
                                    st.session_state.stocks.extend(st.session_state.undo_buffer)
                                    st.session_state.undo_buffer = []
                                    st.session_state.show_undo = False
                                    
                                    # CRITICAL FIX (Robust): Increment key to force total widget recreation
                                    # This bypasses any internal state that Streamlit/BaseWeb might be holding onto
                                    st.session_state.editor_key += 1
                                        
                                    st.toast("Restored deleted stocks!", icon="✅")
                                    st.rerun()
        
        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Save Logic
                        if st.button("💾 Save All Changes", width="stretch"):
                            any_content_changes = False
                            
                            # 1. Update Portfolio-Level Config (Broadcast)
                            portfolio_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                            portfolio_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                            portfolio_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)
                            portfolio_birth_date = st.session_state.get(f"{selected_portfolio}_birth_date", "")
                            portfolio_type = p_type
        
                            mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                            
                            # Check for Config Changes
                            if not user_portfolio_df.empty:
                                fr = user_portfolio_df.iloc[0]
                                if (abs(portfolio_invest - fr.get('portfolio_monthly_invest', 1000.0)) > 0.1 or
                                    portfolio_use_ind != fr.get('portfolio_use_indicators', False) or
                                    portfolio_birth_date != fr.get('portfolio_birth_date', '') or
                                    abs(portfolio_buffett - fr.get('portfolio_buffett_index', 195.0)) > 0.1):
                                    any_content_changes = True
                                    data.loc[mask, 'portfolio_monthly_invest'] = portfolio_invest
                                    data.loc[mask, 'portfolio_use_indicators'] = portfolio_use_ind
                                    data.loc[mask, 'portfolio_buffett_index'] = portfolio_buffett
                                    data.loc[mask, 'portfolio_birth_date'] = portfolio_birth_date
                            
                            # 2. Update Stock Data (Refactored for Data Editor)
                            # We rebuild the rows for this portfolio entirely from the edited_df
                            # This handles Adds, Edits, and Deletes implicitly
                            
                            # First, drop all existing rows for this portfolio
                            data = data[~mask]
                            
                            # Then create new rows from edited_df
                            new_rows = []
                            for _, row in edited_df.reset_index().iterrows():
                                if row['name'] and row['name'] != "__PLACEHOLDER__":
                                     new_rows.append({
                                        "username": username,
                                        "portfolio_name": selected_portfolio,
                                        "stock_name": row['name'],
                                        "current_value": row['current_value'],
                                        "target_allocation": row['target_allocation'],
                                        "tolerance": row['tolerance'],
                                        "expense_ratio": row.get('expense_ratio', 0.0),
                                         "portfolio_monthly_invest": portfolio_invest,
                                        "portfolio_use_indicators": portfolio_use_ind,
                                        "portfolio_buffett_index": portfolio_buffett,
                                        "portfolio_birth_date": portfolio_birth_date,
                                        "portfolio_type": portfolio_type,
                                        "stock_full_name": row.get('full_name', ''),
                                        "sector": row.get('sector', ''),
                                        "industry": row.get('industry', ''),
                                        "country": row.get('country', ''),
                                        "currency": row.get('currency', ''),
                                        "quantity": float(row.get('quantity', 0.0)),
                                        "average_price": float(row.get('average_price', 0.0)),
                                        "dividend_yield": float(row.get('dividend_yield', 0.0))
                                    })
                            
                            if not new_rows:
                                # If empty, add placeholder to keep portfolio alive
                                 new_rows.append({
                                    "username": username,
                                    "portfolio_name": selected_portfolio,
                                    "stock_name": "__PLACEHOLDER__",
                                    "current_value": 0.0,
                                    "target_allocation": 0.0,
                                     "portfolio_monthly_invest": portfolio_invest,
                                    "portfolio_use_indicators": portfolio_use_ind,
                                    "portfolio_buffett_index": portfolio_buffett,
                                    "portfolio_type": portfolio_type,
                                    "stock_full_name": '',
                                    "sector": '',
                                    "industry": '',
                                    "country": '',
                                    "currency": '',
                                    "quantity": 0.0,
                                    "average_price": 0.0,
                                    "dividend_yield": 0.0
                                })
                            
                            updated_data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
                            st.session_state.master_data = updated_data
                            conn.update(worksheet="Portfolios", data=updated_data)
                            
                            st.session_state.has_unsaved_changes = False
                            st.session_state.show_save_success = True
                            st.rerun()
                            
                        if st.session_state.get('show_save_success'):
                            st.success("All changes saved successfully!")
                            st.session_state.show_save_success = False
        
                with col_side:
                    with st.container(border=True):
                        st.subheader("🎯 Action Center")
                        if st.button("🧮 Calculate Allocation", width="stretch"):
                            live_stocks = st.session_state.stocks # Use the updated state
                            total_current_live = sum(s['current_value'] for s in live_stocks)
                            total_target_live = sum(s['target_allocation'] for s in live_stocks)
        
                            if abs(total_target_live - 100.0) > 0.01:
                                st.error(f"Ratios sum to {total_target_live:.1f}%, must be 100%")
                            else:
                                # ... (Calculation Logic reused) ...
                                new_total_theoretical = total_current_live + monthly_investment
                                
                                eligible_stocks = []
                                for stock in live_stocks:
                                    # A stock is eligible if its CURRENT value is less than its post-investment TARGET value (considering tolerance)
                                    # Post-investment target = new_total_theoretical * (target_pct / 100)
                                    target_val_theoretical = new_total_theoretical * (stock['target_allocation'] / 100.0)
                                    tolerance_buffer = new_total_theoretical * (stock.get('tolerance', 0.0) / 100.0)
                                    
                                    if stock['current_value'] < (target_val_theoretical - tolerance_buffer):
                                        eligible_stocks.append(stock)
                                
                                if not eligible_stocks:
                                    st.warning("All stocks are within their tolerance bands! No rebalancing needed.")
                                    eligible_stocks = live_stocks 
        
                                stock_gaps = []
                                for stock in eligible_stocks:
                                    target_val = new_total_theoretical * (stock['target_allocation'] / 100.0)
                                    gap = target_val - stock['current_value']
                                    stock_gaps.append({"Stock": stock['name'], "Target Value": target_val, "Gap": gap, "stock": stock})
                                
                                sorted_gaps = sorted(stock_gaps, key=lambda x: x['Gap'], reverse=True)
                                remaining_investment = float(monthly_investment)
                                
                                # --- REFINED ALLOCATION LOGIC (3-PASS ENFORCEMENT) ---
                                restricted_tickers = ["NVG.PT", "BCP.PT"]
                                is_dividends_p = (p_type == "Dividends") or (selected_portfolio and "dividends" in selected_portfolio.lower())
                                
                                temp_allocs = []
                                # PASS 1: Calculate standard floored investments based on gaps
                                for item in sorted_gaps:
                                    ideal_invest = max(0.0, min(item['Gap'], remaining_investment))
                                    import math
                                    floored_invest = float(math.floor(ideal_invest))
                                    remaining_investment -= floored_invest
                                    temp_allocs.append({"item": item, "invest": floored_invest})
                                
                                # PASS 2: Enforce 10€ rule for restricted stocks in Dividends portfolio
                                # We try to "top up" to 10€ if they got > 0 but < 10
                                if is_dividends_p:
                                    for alloc in temp_allocs:
                                        ticker = str(alloc['item']['Stock']).strip().upper()
                                        if ticker in restricted_tickers:
                                            current_invest = alloc['invest']
                                            if 0 < current_invest < 10:
                                                needed = 10.0 - current_invest
                                                if remaining_investment >= needed:
                                                    # We have enough leftover budget to reach the 10€ minimum
                                                    alloc['invest'] = 10.0
                                                    remaining_investment -= needed
                                                else:
                                                    # Can't afford the minimum, set to 0 and reclaim the floored amount
                                                    remaining_investment += current_invest
                                                    alloc['invest'] = 0.0
                                
                                # PASS 3: Safe Redistribution of the remaining balance (decimals + rejected amounts)
                                if temp_allocs:
                                    dump_idx = -1
                                    # Strategy: Find a safe stock to "dump" the remaining balance into.
                                    # 1. Prefer a non-restricted stock
                                    for i, alloc in enumerate(temp_allocs):
                                        ticker = str(alloc['item']['Stock']).strip().upper()
                                        if not (is_dividends_p and ticker in restricted_tickers):
                                            dump_idx = i
                                            break
                                    
                                    # 2. If no non-restricted stocks, prefer a restricted one that ALREADY has >= 10
                                    if dump_idx == -1:
                                        for i, alloc in enumerate(temp_allocs):
                                            if alloc['invest'] >= 10:
                                                dump_idx = i
                                                break
                                    
                                    # 3. Last resort: Dump into first restricted stock ONLY if it can reach 10€
                                    if dump_idx == -1:
                                        if remaining_investment >= 10:
                                            dump_idx = 0
                                        # If even this fails, it stays in 'remaining_investment' for the user to see
                                    
                                    if dump_idx != -1:
                                        temp_allocs[dump_idx]['invest'] += remaining_investment
                                        remaining_investment = 0.0
                                # --- END REFINED LOGIC ---
                                
                                # Map investments to tickers
                                invest_map = {row['item']['Stock']: row['invest'] for row in temp_allocs}
                                
                                allocations = []
                                new_total_actual = float(total_current_live + monthly_investment)
                                
                                for stock in live_stocks:
                                    ticker = stock['name']
                                    final_invest = invest_map.get(ticker, 0.0)
                                    target_val = new_total_theoretical * (stock['target_allocation'] / 100.0)
                                    new_val = stock['current_value'] + final_invest
                                    
                                    allocations.append({
                                        "Stock": ticker, 
                                        "Current Value": stock['current_value'], 
                                        "Current %": (stock['current_value'] / total_current_live * 100) if total_current_live > 0 else 0, 
                                        "TER %": stock.get('expense_ratio', 0.0),
                                        "Target %": stock['target_allocation'], 
                                        "Target Value": target_val,
                                        "Investment": final_invest, 
                                        "New Value": new_val, 
                                        "New %": (new_val / new_total_actual * 100) if new_total_actual > 0 else 0
                                    })
                                
                                # Sort by Target % (Descending) for consistency with the Management table
                                alloc_df = pd.DataFrame(allocations)
                                if not alloc_df.empty:
                                    alloc_df = alloc_df.sort_values(by="Target %", ascending=False)

                                st.session_state.last_calculation = {"df": alloc_df, "monthly_investment": monthly_investment, "remaining": remaining_investment}
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
                        # Highlight and style. Set Index to Stock to freeze column.
                        styled_df = df.set_index("Stock").style.format(precision=2).set_properties(
                            subset=['Investment'], 
                            **{'background-color': '#24A16F', 'color': '#065F46', 'font-weight': '700', 
                               'border-bottom': '1px solid #065F46'}
                        )
                        # Use st.dataframe for responsive horizontal scrolling
                        st.dataframe(styled_df, use_container_width=True)
                        
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

                                    # --- APPLY NEW VALUES TO PORTFOLIO ---
                                    master_data = st.session_state.master_data.copy()
                                    # Update master_data with New Value for each stock in the current portfolio
                                    for _, row in df.iterrows():
                                        stock_ticker = row['Stock']
                                        new_val = row['New Value']
                                        
                                        mask = (master_data['username'] == username) & \
                                               (master_data['portfolio_name'] == selected_portfolio) & \
                                               (master_data['stock_name'] == stock_ticker)
                                        
                                        if mask.any():
                                            master_data.loc[mask, 'current_value'] = new_val
                                    
                                    # Push updated Portfolio data back to GSheets
                                    conn.update(worksheet="Portfolios", data=master_data)
                                    st.session_state.master_data = master_data
                                    
                                    st.session_state.show_log_success = True
                                    
                                    # Force re-sync of local state so the table reflects the new values
                                    if 'last_selected_portfolio' in st.session_state:
                                        del st.session_state.last_selected_portfolio
                                    st.rerun()
                                except Exception as e: st.error(f"Error: {e}")
                        
                        if st.session_state.get('show_log_success'):
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.success("Logged & Portfolio Updated!")
                            st.balloons()
                            st.session_state.show_log_success = False
        
                    # Charts Row
                    with st.container(border=True):
                        st.subheader("📉 Allocation Visuals")
                        df_plot = df.sort_values('Stock')
                        chart_col1, chart_col2 = st.columns(2)
                        
                        dashboard_colors = ['#FF8B76', '#7BD192', '#5EB1FF', '#FFD166', '#06D6A0']
                        
                        # Mobile Optimization: Place legend horizontal (top/bottom) to save width
                        common_legend = dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                        
                        with chart_col1:
                            fig1 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['Current Value'], hole=0.3, marker=dict(colors=dashboard_colors))])
                            fig1.update_layout(
                                title_text="Current Allocation", 
                                title_font=dict(size=20), 
                                legend=common_legend,
                                font=dict(size=14),
                                margin=dict(t=80, b=80, l=10, r=10),
                                paper_bgcolor='rgba(0,0,0,0)', 
                                plot_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig1, use_container_width=True)
                        with chart_col2:
                            fig2 = go.Figure(data=[go.Pie(labels=df_plot['Stock'], values=df_plot['New Value'], hole=0.3, marker=dict(colors=dashboard_colors))])
                            fig2.update_layout(
                                title_text="After Investment", 
                                title_font=dict(size=20), 
                                legend=common_legend,
                                font=dict(size=14),
                                margin=dict(t=80, b=80, l=10, r=10),
                                paper_bgcolor='rgba(0,0,0,0)', 
                                plot_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig2, use_container_width=True)

        if "📈 Portfolio Details" in tab_map:
            with tab_map["📈 Portfolio Details"]:
                st.session_state.footer_msg = "<b>Data Insight:</b> Visualize your diversification and asset health."
                with st.container(border=True):
                    st.subheader("📈 Detailed Portfolio Information")
                    
                    # Prepare data for Detailed Editor
                    details_df = pd.DataFrame(st.session_state.stocks)
                    if details_df.empty:
                        details_df = pd.DataFrame(columns=["name", "full_name", "sector", "industry", "country", "currency", "current_value", "quantity", "average_price", "dividend_yield"])
                    
                    # Currency Symbol Mapping
                    currency_symbols = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CHF": "Fr", "CAD": "$", "AUD": "$", "DKK": "kr."}
                    primary_currency = details_df['currency'].iloc[0] if not details_df.empty and 'currency' in details_df.columns and details_df['currency'].iloc[0] else "EUR"
                    sym = currency_symbols.get(primary_currency, "€")
                    
                    # Reorder and rename for display
                    display_cols = {
                        "name": "Ticker",
                        "full_name": "Name",
                        "sector": "Sector",
                        "industry": "Industry",
                        "country": "Country",
                        "currency": "Currency",
                        "current_value": "Value",
                        "quantity": "Quantity",
                        "average_price": "Avg. Price",
                        "dividend_yield": "Div. Yield (%)"
                    }
                    
                    # Filtering only the requested columns and renaming
                    details_display_df = details_df[list(display_cols.keys())].rename(columns=display_cols)
                    
                    # Row-level formatting for Avg. Price (Strings with symbols)
                    details_display_df['Avg. Price'] = details_df.apply(
                        lambda x: f"{currency_symbols.get(x['currency'], '€')} {float(x.get('average_price', 0.0)):.2f}", 
                        axis=1
                    )
                    
                    # Freeze Ticker by setting as Index
                    details_display_df.set_index("Ticker", inplace=True)
                    
                    detailed_config = {
                        "Value": st.column_config.NumberColumn("Value (€)", format="€%.2f"),
                        "Quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                        "Avg. Price": st.column_config.TextColumn("Avg. Price"),
                        "Div. Yield (%)": st.column_config.NumberColumn("Div. Yield (%)", format="%.2f%%"),
                    }
                    
                    edited_details_df = st.data_editor(
                        details_display_df,
                        column_config=detailed_config,
                        use_container_width=True,
                        num_rows="dynamic",
                        key=f"details_editor_{st.session_state.editor_key}",
                        on_change=clear_recommendations
                    )
                    
                    # Sync back to session state if edited
                    if not edited_details_df.sort_index().equals(details_display_df.sort_index()):
                        # Map back renamed columns to internal keys
                        reverse_cols = {v: k for k, v in display_cols.items()}
                        # Reset index to get Ticker back into columns before renaming
                        updated_details = edited_details_df.reset_index().rename(columns=reverse_cols)
                        
                        new_stocks_list = []
                        # Existing stocks map to preserve internal rebalancing fields
                        current_stocks_map = {s['name']: s for s in st.session_state.stocks}
                        
                        for _, row in updated_details.iterrows():
                            ticker_val = row['name']
                            ticker = str(ticker_val).strip().upper() if pd.notna(ticker_val) else ""
                            if not ticker or ticker.lower() in ["nan", "none"]:
                                continue
                                
                            # If existing, update numeric and metadata fields
                            if ticker in current_stocks_map:
                                updated_stock = current_stocks_map[ticker].copy()
                                for col in updated_details.columns:
                                    if col == 'average_price':
                                        val_str = str(row[col]).replace(',', '.')
                                        # Keep only digits, dots and minus
                                        clean_val = ''.join(c for c in val_str if c.isdigit() or c in '.-')
                                        if clean_val.count('.') > 1:
                                            # Keep only the last dot
                                            parts = clean_val.split('.')
                                            clean_val = "".join(parts[:-1]) + "." + parts[-1]
                                        try:
                                            updated_stock[col] = float(clean_val) if clean_val else 0.0
                                        except:
                                            updated_stock[col] = 0.0
                                    else:
                                        updated_stock[col] = row[col]
                                new_stocks_list.append(updated_stock)
                            else:
                                # New row added directly in editor
                                new_stock = {
                                    "name": ticker,
                                    "current_value": row.get('current_value', 0.0),
                                    "target_allocation": 0.0,
                                    "tolerance": 2.0,
                                    "expense_ratio": 0.0,
                                    "full_name": row.get('full_name', ''),
                                    "sector": row.get('sector', ''),
                                    "industry": row.get('industry', ''),
                                    "country": row.get('country', ''),
                                    "currency": row.get('currency', 'EUR'),
                                    "quantity": float(row.get('quantity', 0.0)),
                                    "average_price": 0.0,
                                    "dividend_yield": float(row.get('dividend_yield', 0.0))
                                }
                                # Handle average_price string if set
                                if 'average_price' in row:
                                    val_str = str(row['average_price']).replace(',', '.')
                                    clean_val = ''.join(c for c in val_str if c.isdigit() or c in '.-')
                                    if clean_val.count('.') > 1:
                                        parts = clean_val.split('.')
                                        clean_val = "".join(parts[:-1]) + "." + parts[-1]
                                    try:
                                        new_stock['average_price'] = float(clean_val) if clean_val else 0.0
                                    except:
                                        new_stock['average_price'] = 0.0
                                new_stocks_list.append(new_stock)
                        
                        if len(new_stocks_list) < len(st.session_state.stocks):
                            # Identify deleted items
                            updated_names = {s['name'] for s in new_stocks_list}
                            deleted_items = [s for s in st.session_state.stocks if s['name'] not in updated_names]
                            st.session_state.undo_buffer = deleted_items
                            st.session_state.show_undo = True
                            st.toast(f"Deleted {len(deleted_items)} stock(s)", icon="🗑️")
                        else:
                            st.session_state.show_undo = False
                            st.session_state.undo_buffer = []

                        st.session_state.stocks = new_stocks_list
                        st.session_state.has_unsaved_changes = True
                        st.rerun()

                # UNDO AND SAVE BUTTONS
                u_col, s_col = st.columns([1, 1])
                with u_col:
                    if st.session_state.get('show_undo'):
                        if st.button("↩️ Undo Delete", key="undo_details_btn", width="stretch"):
                            if st.session_state.undo_buffer:
                                st.session_state.stocks.extend(st.session_state.undo_buffer)
                                st.session_state.undo_buffer = []
                                st.session_state.show_undo = False
                                st.session_state.editor_key += 1
                                st.toast("Restored deleted stocks!", icon="✅")
                                st.rerun()
                
                with s_col:
                    if st.button("💾 Save All Changes", key="save_details_btn", width="stretch"):
                        # Determine current portfolio config
                        portfolio_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                        portfolio_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                        portfolio_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)
                        portfolio_birth_date = st.session_state.get(f"{selected_portfolio}_birth_date", "")
                        portfolio_type = p_type
                        
                        mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        data = data[~mask]
                        
                        new_rows = []
                        for s in st.session_state.stocks:
                            if s['name'] and s['name'] != "__PLACEHOLDER__":
                                new_rows.append({
                                    "username": username,
                                    "portfolio_name": selected_portfolio,
                                    "stock_name": s['name'],
                                    "current_value": s['current_value'],
                                    "target_allocation": s.get('target_allocation', 0.0),
                                    "tolerance": s.get('tolerance', 2.0),
                                    "expense_ratio": s.get('expense_ratio', 0.0),
                                    "portfolio_monthly_invest": portfolio_invest,
                                    "portfolio_use_indicators": portfolio_use_ind,
                                    "portfolio_buffett_index": portfolio_buffett,
                                    "portfolio_type": portfolio_type,
                                    "stock_full_name": s.get('full_name', ''),
                                    "sector": s.get('sector', ''),
                                    "industry": s.get('industry', ''),
                                    "country": s.get('country', ''),
                                    "currency": s.get('currency', ''),
                                    "quantity": float(s.get('quantity', 0.0)),
                                    "average_price": float(s.get('average_price', 0.0)),
                                    "dividend_yield": float(s.get('dividend_yield', 0.0))
                                })
                        
                        if not new_rows:
                            new_rows.append({
                                "username": username,
                                "portfolio_name": selected_portfolio,
                                "stock_name": "__PLACEHOLDER__",
                                "current_value": 0.0,
                                "target_allocation": 0.0,
                                "portfolio_monthly_invest": portfolio_invest,
                                "portfolio_use_indicators": portfolio_use_ind,
                                "portfolio_buffett_index": portfolio_buffett,
                                "portfolio_birth_date": portfolio_birth_date,
                                "portfolio_type": portfolio_type,
                                "stock_full_name": '', "sector": '', "industry": '', "country": '', "currency": '', "quantity": 0.0, "average_price": 0.0, "dividend_yield": 0.0
                            })
                        
                        updated_data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        
                        st.session_state.has_unsaved_changes = False
                        st.success("Changes saved successfully!")
                        st.balloons()
                        st.rerun()

                # Distribution Charts
                with st.container(border=True):
                    st.subheader("🌍 Portfolio Distributions")
                    
                    # Clean data for plotting (remove placeholders and empty values)
                    plot_data = pd.DataFrame([s for s in st.session_state.stocks if s['name'] != "__PLACEHOLDER__"])
                    
                    if not plot_data.empty:
                        dist_col1, dist_col2, dist_col3 = st.columns(3)
                        
                        chart_theme = dict(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=14),
                            height=350,
                            margin=dict(t=50, b=50, l=10, r=10),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5,
                                font=dict(size=14)
                            )
                        )
                        
                        with dist_col1:
                            # Sector Distribution
                            sector_data = plot_data.groupby('sector')['current_value'].sum().reset_index()
                            sector_data = sector_data[sector_data['sector'] != '']
                            if not sector_data.empty:
                                fig_sector = px.pie(sector_data, values='current_value', names='sector', hole=0.4)
                                fig_sector.update_layout(chart_theme, title=dict(text="By Sector", x=0.5, font=dict(size=20)))
                                fig_sector.update_traces(textposition='inside', textinfo='percent+label', insidetextorientation='horizontal')
                                fig_sector.update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
                                st.plotly_chart(fig_sector, use_container_width=True)
                            else:
                                st.info("No sector data available.")
                                
                        with dist_col2:
                            # Industry Distribution
                            ind_data = plot_data.groupby('industry')['current_value'].sum().reset_index()
                            ind_data = ind_data[ind_data['industry'] != '']
                            if not ind_data.empty:
                                fig_ind = px.pie(ind_data, values='current_value', names='industry', hole=0.4)
                                fig_ind.update_layout(chart_theme, title=dict(text="By Industry", x=0.5, font=dict(size=20)))
                                fig_ind.update_traces(textposition='inside', textinfo='percent+label', insidetextorientation='horizontal')
                                fig_ind.update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
                                st.plotly_chart(fig_ind, use_container_width=True)
                            else:
                                st.info("No industry data available.")
                                
                        with dist_col3:
                            # Country Distribution
                            country_data = plot_data.groupby('country')['current_value'].sum().reset_index()
                            country_data = country_data[country_data['country'] != '']
                            if not country_data.empty:
                                fig_country = px.pie(country_data, values='current_value', names='country', hole=0.4)
                                fig_country.update_layout(chart_theme, title=dict(text="By Country", x=0.5, font=dict(size=20)))
                                fig_country.update_traces(textposition='inside', textinfo='percent+label', insidetextorientation='horizontal')
                                fig_country.update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
                                st.plotly_chart(fig_country, use_container_width=True)
                            else:
                                st.info("No country data available.")
                    else:
                        st.info("Add stocks to see distributions.")

        if "💰 Dividend Tracker" in tab_map:
            with tab_map["💰 Dividend Tracker"]:
                st.session_state.footer_msg = "<b>Passive Income:</b> Track your dividend yields and growth."
                st.subheader("💰 Dividend Tracker")
                d_col1, d_col2 = st.columns([1, 2])
                
                with d_col1:
                    with st.container(border=True):
                        st.markdown("### ➕ Record Dividend")
                        from datetime import datetime
                        div_date = st.date_input("Date", value=datetime.today())
                        
                        current_portfolio_stocks = [s['name'] for s in st.session_state.stocks if s['name'] != "__PLACEHOLDER__"]
                        if not current_portfolio_stocks:
                            st.warning("Add stocks to your portfolio first.")
                            div_ticker = None
                        else:
                            div_ticker = st.selectbox("Ticker", options=current_portfolio_stocks)
                        
                        div_amount = st.number_input("Amount (€)", min_value=0.0, step=0.01)
                        
                        if st.button("Add Record", width="stretch"):
                            if div_ticker and div_amount > 0:
                                new_div = {
                                    "date": str(div_date),
                                    "ticker": div_ticker,
                                    "amount": div_amount,
                                    "portfolio_name": selected_portfolio,
                                    "username": username
                                }
                                new_row_df = pd.DataFrame([new_div])
                                st.session_state.dividends = pd.concat([st.session_state.dividends, new_row_df], ignore_index=True)
                                conn.update(worksheet="Dividends", data=st.session_state.dividends)
                                st.success("Dividend Recorded!")
                                st.rerun()
                            else:
                                st.error("Please select a ticker and enter an amount.")
                
                with d_col2:
                    with st.container(border=True):
                        st.markdown("### 📈 Monthly Dividends")
                        df_divs = st.session_state.dividends
                        if not df_divs.empty:
                            df_divs['amount'] = pd.to_numeric(df_divs['amount'], errors='coerce').fillna(0.0)
                            df_divs['date'] = pd.to_datetime(df_divs['date'], errors='coerce')
                            mask = (df_divs['username'] == username) & (df_divs['portfolio_name'] == selected_portfolio)
                            my_divs = df_divs[mask].copy()
                            if not my_divs.empty:
                                # Filter for Current and Previous Year only
                                current_year = datetime.now().year
                                my_divs = my_divs[my_divs['date'].dt.year >= (current_year - 1)]
                                
                                if my_divs.empty:
                                    st.info(f"No dividends found for {current_year-1} or {current_year}.")
                                else:
                                    my_divs['Year'] = my_divs['date'].dt.year.astype(str)
                                    
                                    # Ticker Filter
                                    available_tickers = sorted(my_divs['ticker'].unique().tolist())
                                    filter_ticker = st.selectbox("🔍 Filter by Ticker", options=["All Data"] + available_tickers)
                                    
                                    if filter_ticker != "All Data":
                                        my_divs = my_divs[my_divs['ticker'] == filter_ticker]
                                        if my_divs.empty:
                                            st.warning(f"No data for {filter_ticker} in the selected period.")
                                            st.stop()
                                
                                # Calculate Yearly Totals
                                current_year_str = str(current_year)
                                prev_year_str = str(current_year - 1)
                                
                                total_current_year = my_divs[my_divs['Year'] == current_year_str]['amount'].sum()
                                total_prev_year = my_divs[my_divs['Year'] == prev_year_str]['amount'].sum()
                                
                                # Display Totals Side-by-Side
                                metric_col1, metric_col2 = st.columns(2)
                                with metric_col1:
                                    st.metric(label=f"💰 Total Dividends ({current_year})", value=f"€{total_current_year:,.2f}")
                                with metric_col2:
                                    st.metric(label=f"💰 Total Dividends ({current_year-1})", value=f"€{total_prev_year:,.2f}")
                                
                                my_divs['Month'] = my_divs['date'].dt.strftime('%b')
                                my_divs['MonthNum'] = my_divs['date'].dt.month
                                
                                # Aggregated stats
                                actual_stats = my_divs.groupby(['Year', 'Month', 'MonthNum'])['amount'].sum().reset_index()
                                
                                # Create a template for all 12 months for BOTH years to ensure a full X-axis
                                import calendar
                                all_months = [calendar.month_name[i][:3] for i in range(1, 13)] # ['Jan', 'Feb', ...]
                                
                                template_rows = []
                                for yr in [str(current_year), str(current_year-1)]:
                                    for i, m in enumerate(all_months):
                                        template_rows.append({'Year': yr, 'Month': m, 'MonthNum': i+1})
                                
                                template_df = pd.DataFrame(template_rows)
                                
                                # Merge actual data into template
                                monthly_stats = pd.merge(template_df, actual_stats, on=['Year', 'Month', 'MonthNum'], how='left').fillna(0.0)
                                
                                # Sort for plotting: Year descending (Previous Year first in group usually depends on plotly, but keeping Month order is key)
                                monthly_stats = monthly_stats.sort_values(['MonthNum', 'Year'])
                                
                                st.markdown("**Dividends Received (Yearly Comparison)**")
                                fig_div = px.bar(monthly_stats, x='Month', y='amount', color='Year', barmode='group', labels={'amount': 'Amount (€)', 'Month': 'Month'}, text='amount')
                                fig_div.update_traces(texttemplate='€%{y:.2f}', textposition='inside', textangle=-90, textfont_size=16)
                                fig_div.update_layout(
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                    font=dict(size=16), 
                                    margin=dict(t=10, b=50, l=10, r=10), 
                                    paper_bgcolor='rgba(0,0,0,0)', 
                                    plot_bgcolor='rgba(0,0,0,0)'
                                )
                                st.plotly_chart(fig_div, use_container_width=True, config={'displayModeBar': False})
                                with st.expander("Dividend History"):
                                    st.dataframe(my_divs[['date', 'ticker', 'amount']].sort_values('date', ascending=False), use_container_width=True)
                            else:
                                st.info("No dividends recorded for this portfolio yet.")
                        else:
                            st.info("No dividends recorded yet.")

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
    footer_text = st.session_state.get('footer_msg', "Maintain your risk profile with disciplined allocation.")
    st.markdown(
        f"""
        <div style='text-align: center; color: #9CA3AF; padding: 20px; font-size: 0.8rem;'>
        💡 {footer_text}<br>
        <small>Educational purposes only. Always consult a financial advisor.</small>
        </div>
        """,
        unsafe_allow_html=True
    )
