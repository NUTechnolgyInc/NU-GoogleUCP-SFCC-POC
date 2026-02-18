# Deployment Guide

This project is configured as a monorepo with the following deployment architecture:
- **Frontend**: React (Vite) deployed to **Vercel**.
- **Backend**: Python (AI Agent) deployed to **Google Cloud Run**.
- **Database**: **Turso (libsql)**.

---

## 1. Vercel Configuration (Frontend)

Vercel handles the static deployment and proxies API requests to Cloud Run.

### Settings in Vercel Dashboard:
- **Root Directory**: `apps/chat-client`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Environment Variables**:
  - `USE_SCAPI`: `true`

---

## 2. GitHub Configuration (Automation)

The GitHub Action in `.github/workflows/deploy.yml` triggers a Google Cloud Build to deploy the backend.

### Required GitHub Secrets:
Go to **Settings > Secrets and variables > Actions** and add the following:

| Secret Name | Description | Example / Source |
| :--- | :--- | :--- |
| `GCP_PROJECT_ID` | Your Google Cloud Project ID | `numart-gcp-456121` |
| `GCP_SA_KEY` | JSON Key for Service Account | Service Account with Cloud Run/Build roles |
| `GOOGLE_API_KEY` | Google Gemini API Key | Google AI Studio |
| `TURSO_URL` | Your Turso Database URL | `https://nu-ucp-poc...turso.io` |
| `TURSO_AUTH_TOKEN` | Turso Authentication Token | Turso Dashboard |
| `SCAPI_HOST` | Salesforce SCAPI Host | See `.env` |
| `SCAPI_ORG_ID` | Salesforce Org ID | See `.env` |
| `SCAPI_CLIENT_ID` | Salesforce Client ID | See `.env` |
| `SCAPI_CLIENT_SECRET` | Salesforce Client Secret | See `.env` |
| `SCAPI_CHANNEL_ID` | Salesforce Channel ID | See `.env` |
| `SCAPI_SITE_ID` | Salesforce Site ID | See `.env` |

---

## 3. Google Cloud Configuration (Backend)

The backend is built using the root `Dockerfile` and `cloudbuild.yaml`.

### Permissions Needed:
Ensure the Service Account used for the GitHub Action has these roles:
- `Cloud Build Editor`
- `Cloud Run Admin`
- `Service Account User`
- `Artifact Registry Writer`

### Manual Deploy:
You can trigger a manual deployment from the **Actions** tab in GitHub by selecting the **"Trigger Cloud Build"** workflow.

---

## 🛠️ Local Testing
To test the full flow locally:
1. Start Backend: `cd apps/business_agent && source venv/bin/activate && export PYTHONPATH=$PYTHONPATH:$(pwd)/src && python -m business_agent.main`
2. Start Frontend: `cd apps/chat-client && npm run dev`
