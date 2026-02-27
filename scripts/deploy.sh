#!/usr/bin/env bash
# =============================================================================
# Deploy FCT Proposal Engine to GCP Cloud Run
# Usage: ./scripts/deploy.sh [--init]
# =============================================================================

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-fct-proposal-engine}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-fct-engine-api}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/fct-engine"

echo "🚀 Deploying FCT Proposal Engine"
echo "   Project:  ${PROJECT_ID}"
echo "   Region:   ${REGION}"
echo "   Service:  ${SERVICE_NAME}"
echo ""

# --- First-time setup ---
if [[ "${1:-}" == "--init" ]]; then
    echo "📦 Initializing GCP infrastructure..."

    gcloud services enable \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        cloudbuild.googleapis.com

    gcloud artifacts repositories create fct-engine \
        --repository-format=docker \
        --location="${REGION}" 2>/dev/null || true

    echo "🔐 Creating secrets (add values via GCP Console or gcloud)..."
    for secret in anthropic-api-key openai-api-key google-api-key huggingface-api-key scopus-api-key; do
        gcloud secrets create "${secret}" --replication-policy="automatic" 2>/dev/null || true
    done

    echo "✅ Init complete. Add secret values, then re-run without --init."
    exit 0
fi

# --- Build & Push ---
echo "🔨 Building container..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker build -t "${REGISTRY}/${SERVICE_NAME}:latest" .
docker push "${REGISTRY}/${SERVICE_NAME}:latest"

# --- Deploy ---
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${REGISTRY}/${SERVICE_NAME}:latest" \
    --region "${REGION}" \
    --platform managed \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --concurrency 10 \
    --min-instances 0 \
    --max-instances 3 \
    --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,GOOGLE_API_KEY=google-api-key:latest,HUGGINGFACE_API_KEY=huggingface-api-key:latest,SCOPUS_API_KEY=scopus-api-key:latest" \
    --allow-unauthenticated

URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")
echo ""
echo "✅ Deployed successfully!"
echo "   URL: ${URL}"
echo "   Health: ${URL}/health"
echo "   Docs:   ${URL}/docs"
