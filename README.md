# 💰 Portfolio Allocation Calculator

A Streamlit web application for calculating optimal investment allocations to rebalance your stock portfolio.

## Features

- 📊 Track multiple stocks with current values and target allocations
- 💵 Calculate monthly investment distribution
- 📈 Visual comparison of current vs. target allocation
- ➕ Add/remove stocks dynamically
- 🔄 Real-time portfolio rebalancing calculations

## Quick Start with Docker

### Option 1: Using Docker Compose (Recommended)

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Option 2: Using Docker Directly

```bash
# Build the image
docker build -t portfolio-calculator .

# Run the container
docker run -p 8501:8501 portfolio-calculator
```

Access the app at: **http://localhost:8501**

## Deployment Options

### 1. Streamlit Community Cloud (Free & Easiest)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Deploy! You'll get a public URL like: `https://yourapp.streamlit.app`

**No Docker needed** - Streamlit Cloud handles everything.

### 2. Railway.app

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

You'll get a public URL automatically.

### 3. Render.com

1. Create a `render.yaml`:
```yaml
services:
  - type: web
    name: portfolio-calculator
    env: docker
    plan: free
```

2. Connect your GitHub repo at [render.com](https://render.com)
3. Deploy!

### 4. AWS/Google Cloud/Azure

Deploy using their container services:
- **AWS**: ECS Fargate or App Runner
- **Google Cloud**: Cloud Run
- **Azure**: Container Instances

### 5. Your Own Server (VPS)

```bash
# On your server with a public IP
git clone your-repo
cd your-repo

# Run with docker-compose
docker-compose up -d

# Optional: Set up nginx as reverse proxy
# Point your domain to the server
```

### 6. Temporary Testing (ngrok)

For testing before deployment:

```bash
# Run the app locally
docker-compose up

# In another terminal, expose it
ngrok http 8501
```

You'll get a temporary public URL.

## Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## How to Use

1. **Configure Stocks**: 
   - View your current stocks in the main area
   - Edit current values and target allocations
   - Add new stocks via the sidebar

2. **Set Investment Amount**: 
   - Enter your monthly investment in the sidebar

3. **Calculate**: 
   - Click "Calculate Investment Allocation"
   - View recommended amounts to invest in each stock
   - See visual comparisons of current vs. target allocation

4. **Rebalance**: 
   - Follow the investment recommendations
   - The app shows you exactly how much to invest in each stock

## Configuration

### Port Configuration

To change the default port (8501):

**Docker Compose:**
```yaml
ports:
  - "3000:8501"  # Access at localhost:3000
```

**Docker:**
```bash
docker run -p 3000:8501 portfolio-calculator
```

### Environment Variables

Create a `.streamlit/config.toml` file for customization:

```toml
[server]
port = 8501
address = "0.0.0.0"

[theme]
primaryColor = "#F63366"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
├── .dockerignore        # Docker ignore patterns
└── README.md            # This file
```

## Troubleshooting

### Port already in use
```bash
# Find and kill process using port 8501
lsof -ti:8501 | xargs kill -9

# Or use a different port
docker run -p 8502:8501 portfolio-calculator
```

### Container won't start
```bash
# Check logs
docker logs portfolio-calculator

# Rebuild without cache
docker-compose build --no-cache
```

### Can't access from other devices
Make sure your firewall allows port 8501, or configure your router to forward the port.

## Security Notes

- This app stores data in session state (temporary, not persistent)
- For production, consider adding authentication
- Don't expose sensitive financial data on public deployments
- Use HTTPS in production (handled automatically by most cloud platforms)

## Customization

### Adding Persistence

To save portfolio data between sessions, you can add:
- SQLite database
- PostgreSQL (for cloud deployments)
- Cloud storage (AWS S3, Google Cloud Storage)

### Adding Features

Some ideas:
- Historical performance tracking
- CSV import/export
- Multiple portfolio support
- Alert notifications
- API integration with brokers

## License

MIT License - Feel free to use and modify!

## Support

For issues or questions:
- Check Docker logs: `docker-compose logs`
- Ensure port 8501 is available
- Verify all files are in the correct location

---

**Disclaimer**: This tool is for educational purposes only. Always consult with a financial advisor before making investment decisions.
