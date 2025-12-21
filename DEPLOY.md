# Deploying to Railway

This project is configured for easy deployment on [Railway](https://railway.app/).

## Prerequisites

- A GitHub account
- A Railway account (can sign up with GitHub)

## Deployment Steps (Dashboard)

1.  **Fork/Push this repository** to your GitHub account (if you haven't already).
2.  Go to your [Railway Dashboard](https://railway.app/dashboard).
3.  Click **"New Project"** -> **"Deploy from GitHub repo"**.
4.  Select this repository (`portfolio-rebalancing`).
5.  Railway will automatically detect the `Dockerfile` and start building.

## Configuration

The application is configured to listen on the port provided by Railway (via the `PORT` environment variable). No additional environment variables are strictly required for the app to run.

- **Port**: defaults to `8501` locally, or uses `PORT` if set by Railway.
- **Address**: `0.0.0.0` (required for containerized apps).

## Verification

Once deployed, Railway will provide a `.railway.app` URL (or you can add a custom domain). Open that URL to see your Portfolio Rebalancing Calculator live.
