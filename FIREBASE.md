# Firestore data store

Portfolio data lives in **Firestore** (four collections, one document each).

## Collections

| Collection | Document | Content |
|------------|----------|---------|
| `Portfolios` | `data` | Field `rows`: array of holding rows (former Portfolios sheet) |
| `StockPurchases` | `data` | Stock purchase units |
| `Dividends` | `data` | Dividend records |
| `InvestmentLog` | `data` | Allocation log history |

You can create empty collections in the Firebase console; the app creates the `data` document on first write.

## Credentials

Use a **service account** with the **Cloud Datastore User** or **Firebase Admin** role on your project.

**Not** the Web app config from Firebase (the snippet with `apiKey`, `authDomain`, `projectId` only). You need the **private key JSON** from **Project settings → Service accounts → Generate new private key** (`type`, `private_key`, `client_email`, `project_id`).

**Option A — environment variable (API / Streamlit / Docker)**

```bash
export FIREBASE_PROJECT_ID="your-gcp-project-id"
export FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"...",...}'
```

**Option B — file path**

```bash
export FIREBASE_PROJECT_ID="your-gcp-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**Option C — Streamlit secrets** (`.streamlit/secrets.toml`)

```toml
[firebase]
project_id = "your-gcp-project-id"
credentials_json = '''{"type":"service_account",...}'''
```

During migration you can keep existing `GSHEETS_*` vars; the app still accepts the same service account JSON if it has Firestore access.

## Diagnose empty data

```bash
.venv/bin/python scripts/diagnose_data.py
```

If you see `apiKey` in the error, fix `.env` (see `.env.example`) before migrating.

## Migrate from Google Sheets (one time)

With Sheets credentials still configured:

```bash
pip install gspread gspread-dataframe google-auth  # if removed from venv
python scripts/migrate_gsheets_to_firestore.py
```

This reads all four worksheets and writes them to Firestore.

## Enable Firestore (required once per GCP project)

If migration or the API fails with **“Cloud Firestore API has not been used… or it is disabled”**:

1. Open [Enable Cloud Firestore API](https://console.developers.google.com/apis/api/firestore.googleapis.com/overview?project=portfolio-app-481920) (replace `portfolio-app-481920` with your `FIREBASE_PROJECT_ID` / `project_id` from the JSON).
2. Click **Enable** and wait 2–5 minutes.
3. In [Firebase Console](https://console.firebase.google.com/) → your project → **Build** → **Firestore Database** → **Create database** (Native mode, pick a region).
4. Ensure `FIREBASE_PROJECT_ID` in `.env` matches the project where Firestore was created (same as `project_id` in the service account JSON).

Service account needs **Cloud Datastore User** or **Firebase Admin** on that project.

Then re-run:

```bash
python scripts/migrate_gsheets_to_firestore.py
```

## Mobile app (client SDK — no service account on device)

The Expo app uses **`EXPO_PUBLIC_FIREBASE_*`** (same pattern as your expense app). See `mobile/.env.example` and [MOBILE.md](MOBILE.md).

Deploy **`firestore.rules`** so authenticated users can read/write the four worksheet collections:

```bash
npx firebase-tools login
npx firebase-tools deploy --only firestore:rules
```

(`firebase.json` and `.firebaserc` at repo root; default project `expenseapp-df745`.)

## Run (Streamlit / optional API)

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
streamlit run app.py
```

Docker: set `FIREBASE_PROJECT_ID` and `FIREBASE_CREDENTIALS_JSON` on `portfolio-api` (see `docker-compose.yml`).
