# btc-tools

BTC Tools provides a Streamlit dashboard and supporting utilities for tracking
Bitcoin technical indicators using Kraken market data via `ccxt`.

## Quickstart

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Run with Docker

Build and start the dashboard in a self-contained container:

```bash
docker compose up --build
```

This uses the provided `Dockerfile.streamlit` and maps the service to
<http://localhost:8501>. The container is configured to restart automatically,
matching always-on hosts like project hubs.

## Permanent hosting

- Deploy the Docker image automatically with the provided GitHub Actions workflow
  (publishes to GitHub Container Registry as
  `ghcr.io/<owner>/btc-tools-dashboard:latest`).
- Or follow the deployment guide for Streamlit Community Cloud, Hugging Face
  Spaces, and other hosting targets.

See [docs/deployment.md](docs/deployment.md) for detailed instructions.
