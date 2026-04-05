# 💰 Professional Portfolio Rebalancing Hub

A comprehensive, multi-strategy wealth management platform built with **Streamlit**. Designed for investors who manage multiple sub-portfolios with different strategic goals, ranging from long-term accumulation to alternative asset funding and child savings.

---

## 🚀 Core Strategies

### 📈 Accumulation (Market-Adaptive)
- **Buffett Indicator Integration**: Dynamically adjusts target allocations for SPYL.DE, IXUA.DE, and VFEA.DE based on the US Market Cap to GDP ratio.
- **Smart Budgeting**: Automatically diverts 7% of its monthly budget to the **Gold & Bonds** strategy only when needed.

### 🏆 Dividends (Yield-Focused)
- **Strategic Funding**: Diverts 10% of its total budget to the **Gold & Bonds** strategy to maintain alternative asset exposure.

### 🛡️ Gold & Bonds (Global Hedge)
- **Dynamic Diversion**: Intelligently monitors the global portfolio status. If the Gold & Bonds allocation is already on target, it cancels diversions from other portfolios to maximize stock growth.
- **Unified Management**: Manages EGNL.UK (Gold) and IBTE.UK (Bonds) as a single strategic unit.

### 👶 Kids (Age-Based Savings)
- **Automated Target-Date**: Shifts allocation between VWCE.DE (Stocks) and VAGF.DE (Bonds) automatically based on the child's age, increasing safety as they get older.

---

## ✨ Key Features

- **Premium UI/UX**: Dark-themed dashboard with sleek KPI cards for "Weighted TER", "Target Status", and "Strategic Gaps".
- **GSheets Integration**: All portfolio data, market indicators, and dividend histories are persisted in Google Sheets for easy access and security.
- **Interactive Management**: Use on-the-fly data editors to manage stocks, update current values, and manually override targets when necessary.
- **Currency Support**: Automatic handling of multiple currencies (EUR, USD, GBP, etc.) with localized symbol mapping.
- **Visual Analytics**: Dynamic Plotly charts showing "Current vs Target" distributions and "Before/After" rebalancing impact.

---

## 🛠️ Technical Stack

- **Frontend**: Streamlit
- **Data Engine**: Pandas & NumPy
- **Visuals**: Plotly (Pie Charts & Dashboards)
- **Database**: Google Sheets (via `streamlit-gsheets`)
- **Environment**: Docker & Python 3.11+

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- A Google Cloud project with Google Sheets API enabled.
- A service account JSON key for authentication.

### 2. Environment Configuration
Create a `.streamlit/secrets.toml` file or set environment variables:

```toml
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/your-id"
type = "service_account"
project_id = "your-project-id"
private_key = "-----BEGIN PRIVATE KEY-----\n..."
client_email = "your-service-account@..."
# Add other GSheets client fields...
```

### 3. Running with Docker (Recommended)
```bash
# Build and run
docker-compose up -d --build
```
The app will be available at `http://localhost:8501`.

### 4. Local Development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔒 Security & Persistence
The application uses a robust session-state synchronization mechanism. Edits made in the management tables are merged back into the master state without losing metadata (sectors, countries, etc.), and can be committed to the cloud database with a single click.

---

## ⚖️ Disclaimer
*This tool is for educational purposes only. It is not financial advice. Rebalancing strategies are based on mathematical models and should be reviewed by a professional financial advisor before execution.*
