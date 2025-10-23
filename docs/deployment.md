# Deployment Guide

This project ships with a Streamlit dashboard located at `dashboard/app.py`. The
sections below walk through a few zero-cost and low-maintenance options for
keeping the site running continuously, similar to other AI project hubs.

## Option 1 – Streamlit Community Cloud (recommended)

The [Streamlit Community Cloud](https://streamlit.io/cloud) offers free hosting
for public Streamlit applications and automatically keeps the service alive.

1. **Prepare your repository**
   - Push this project to a public GitHub repository (forking it is fine).
   - Ensure the repo contains `dashboard/app.py` and `requirements.txt` at the
     root (already present in this project).
2. **Create the app on Streamlit Cloud**
   - Sign in at <https://streamlit.io/cloud> using your GitHub account.
   - Click **New app**, pick the repository, select the default branch, and set
     the main file path to `dashboard/app.py`.
   - The build system will auto-install dependencies from `requirements.txt` and
     start the app. The site receives a stable public URL that stays active as
     long as it has occasional traffic (Streamlit periodically wakes the app).
3. **Optional: configure secrets / settings**
   - If you need to override the timeframe or other values, edit
     `conf/settings.yml` in your repository.
   - If you later add credentials or API keys, open the Streamlit Cloud app,
     navigate to **Settings → Secrets**, and paste the key/value pairs in TOML
     format.

The app will restart automatically whenever you push new commits to the selected
branch, so keeping it updated is just a matter of pushing to GitHub.

## Option 2 – GitHub Actions + GitHub Container Registry

The repository now includes a workflow at
`.github/workflows/build-docker.yml` that continuously builds the production
image using `Dockerfile.streamlit`.

1. Enable GitHub Packages for your account/organization (Settings → Packages).
2. Push this repository to GitHub and ensure the `main` branch is your default.
3. On each push to `main`, the workflow builds `ghcr.io/<owner>/btc-tools-dashboard:latest`
   using the checked-in Dockerfile and publishes it to GHCR. You can also start a
   manual build from the **Actions** tab via the **Run workflow** button.
4. Deploy the published image to any container host (Fly.io, Render, Railway,
   Google Cloud Run, a VPS, etc.) and configure it to restart on failure. The
   container automatically exposes Streamlit on port 8501 and binds to
   `0.0.0.0`, so no additional entrypoint work is required.

## Option 3 – Hugging Face Spaces

[Hugging Face Spaces](https://huggingface.co/spaces) can also host Streamlit apps
permanently with minimal configuration.

1. Create a new **Space** and choose the **Streamlit** template.
2. Set the `App file` to `dashboard/app.py` and upload the project files (or
   connect the Space to your GitHub repo via the **Files and versions** tab).
3. Spaces automatically install the packages from `requirements.txt` and expose
   the application at `https://<space-name>.hf.space`.
4. Enable **Hardware → Keep alive** if you want the project to stay running even
   without visitors (requires HF Pro).

## Option 4 – Self-host with Docker Compose

If you prefer to run the dashboard yourself, use the included Docker artifacts.

```bash
docker compose up --build -d
```

The `compose.yaml` file wraps the `Dockerfile.streamlit` image and maps the
service to port 8501. The container is set to `restart: unless-stopped` so it
automatically comes back online if the host reboots.

## Keeping the app healthy

Regardless of the hosting option you choose:

- Monitor logs for connectivity limits imposed by the Kraken API (ccxt handles
  rate limiting, but external providers may throttle sustained heavy use).
- Schedule occasional visits or use the hosting provider’s “keep warm” toggle to
  prevent free tiers from sleeping the app.
- When updating dependencies, test locally with `streamlit run dashboard/app.py`
  (or `docker compose up --build`) before pushing to production.

With the managed options above—or your own container host—you can achieve an
always-on experience similar to other AI dashboards hosted on project hubs.
