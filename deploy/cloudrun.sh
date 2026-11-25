#!/usr/bin/env bash
# Deploy the Brand Bot API to Google Cloud Run. Safe to re-run: it creates what's missing and updates the rest.
#
#   PROJECT_ID=my-project WEB_URL=https://brandbot.vercel.app ./deploy/cloudrun.sh
#
# Needs: gcloud (logged in), a Postgres database reachable from Cloud Run (Cloud SQL, Neon, Supabase, ...).
# Secrets live in Secret Manager. On the first run the script creates them from these environment variables
# (SECRET_KEY and CRON_SECRET are generated when unset); later runs leave existing secrets alone.
#   DATABASE_URL       postgresql+asyncpg://user:pass@host:5432/brandbot   (required)
#   GOOGLE_API_KEY     Gemini                                               (required)
#   TAVILY_API_KEY     web research                                         (required)
#   LANGSMITH_API_KEY  tracing                                              (optional)
#   LINKEDIN_CLIENT_SECRET, X_CLIENT_SECRET, THREADS_APP_SECRET, INSTAGRAM_APP_SECRET   (optional)
# Platform client ids are not secret: pass LINKEDIN_CLIENT_ID, X_CLIENT_ID, THREADS_APP_ID, INSTAGRAM_APP_ID.
#
# Cloud SQL instead of a public Postgres: CLOUDSQL_INSTANCE=project:region:instance and
#   DATABASE_URL=postgresql+asyncpg://user:pass@/brandbot?host=/cloudsql/project:region:instance
set -euo pipefail

# Settings and keys can also live in deploy/secrets.env (see secrets.env.example; git ignores it).
SECRETS_FILE="$(dirname "$0")/secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
  # Read KEY=value lines literally (not as shell code), so URLs with & or ? need no quoting.
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*([A-Z_][A-Z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}" value="${BASH_REMATCH[2]}"
    value="${value%$'\r'}"; value="${value#[\"\']}"; value="${value%[\"\']}"
    [[ -z "${!key:-}" ]] && export "$key=$value"  # variables already set in the shell win
  done <"$SECRETS_FILE"
fi

: "${PROJECT_ID:?Set PROJECT_ID}"
: "${WEB_URL:?Set WEB_URL, where the web app runs, e.g. https://brandbot.vercel.app}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-brandbot-api}"
REPO="${REPO:-brandbot}"
BUCKET="${BUCKET:-${PROJECT_ID}-brandbot-media}"
SA_NAME="${SA_NAME:-brandbot-api}"
MAX_INSTANCES="${MAX_INSTANCES:-5}"
LANGSMITH_PROJECT="${LANGSMITH_PROJECT:-brand-bot}"
WEB_URL="${WEB_URL%/}"
# The browser reaches the API through the web app (/api), so OAuth callbacks and image URLs use that address.
API_PUBLIC_URL="${API_PUBLIC_URL:-${WEB_URL}/api}"

SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
gc() { gcloud --project "$PROJECT_ID" --quiet "$@"; }
step() { printf '\n==> %s\n' "$*"; }

step "Enabling APIs"
gc services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com storage.googleapis.com

step "Service account ${SA}"
gc iam service-accounts describe "$SA" >/dev/null 2>&1 ||
  gc iam service-accounts create "$SA_NAME" --display-name "Brand Bot API"

step "Media bucket gs://${BUCKET} (private; the API serves images)"
gc storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 ||
  gc storage buckets create "gs://${BUCKET}" --location "$REGION" --uniform-bucket-level-access --public-access-prevention
gc storage buckets add-iam-policy-binding "gs://${BUCKET}" --member "serviceAccount:${SA}" --role roles/storage.objectUser >/dev/null

step "Secrets"
ensure_secret() { # name, value (empty = only if it already exists)
  local name="$1" value="${2:-}"
  if ! gc secrets describe "$name" >/dev/null 2>&1; then
    [[ -z "$value" ]] && return 1
    printf '%s' "$value" | gc secrets create "$name" --replication-policy automatic --data-file=- >/dev/null
    echo "  created $name"
  fi
  gc secrets add-iam-policy-binding "$name" --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor >/dev/null
}
ensure_secret brandbot-database-url "${DATABASE_URL:-}" || { echo "Set DATABASE_URL for the first deploy."; exit 1; }
ensure_secret brandbot-secret-key "${SECRET_KEY:-$(openssl rand -hex 32)}"
ensure_secret brandbot-cron-secret "${CRON_SECRET:-$(openssl rand -hex 24)}"
ensure_secret brandbot-google-api-key "${GOOGLE_API_KEY:-}" || { echo "Set GOOGLE_API_KEY for the first deploy."; exit 1; }
ensure_secret brandbot-tavily-api-key "${TAVILY_API_KEY:-}" || { echo "Set TAVILY_API_KEY for the first deploy."; exit 1; }
SECRETS="DATABASE_URL=brandbot-database-url:latest,SECRET_KEY=brandbot-secret-key:latest,CRON_SECRET=brandbot-cron-secret:latest"
SECRETS+=",GOOGLE_API_KEY=brandbot-google-api-key:latest,TAVILY_API_KEY=brandbot-tavily-api-key:latest"
TRACING=false
if ensure_secret brandbot-langsmith-api-key "${LANGSMITH_API_KEY:-}"; then
  SECRETS+=",LANGSMITH_API_KEY=brandbot-langsmith-api-key:latest"; TRACING=true
fi
for pair in LINKEDIN_CLIENT_SECRET:brandbot-linkedin-secret X_CLIENT_SECRET:brandbot-x-secret \
            THREADS_APP_SECRET:brandbot-threads-secret INSTAGRAM_APP_SECRET:brandbot-instagram-secret; do
  var="${pair%%:*}" name="${pair#*:}"
  if ensure_secret "$name" "${!var:-}"; then SECRETS+=",${var}=${name}:latest"; fi
done

step "Building ${IMAGE}"
gc artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gc artifacts repositories create "$REPO" --location "$REGION" --repository-format docker
gc builds submit --region "$REGION" --tag "$IMAGE" "$(dirname "$0")/.."

SQL_FLAGS=()
[[ -n "${CLOUDSQL_INSTANCE:-}" ]] && SQL_FLAGS=(--set-cloudsql-instances "$CLOUDSQL_INSTANCE")

step "Migrating the database"
gc run jobs deploy brandbot-migrate --region "$REGION" --image "$IMAGE" --service-account "$SA" \
  --command alembic --args upgrade,head --set-secrets "DATABASE_URL=brandbot-database-url:latest" \
  --max-retries 0 --task-timeout 10m ${SQL_FLAGS[@]+"${SQL_FLAGS[@]}"}
gc run jobs execute brandbot-migrate --region "$REGION" --wait

step "Deploying ${SERVICE}"
ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
cat >"$ENV_FILE" <<EOF
ENVIRONMENT: production
LOG_FORMAT: json
GOOGLE_CLOUD_PROJECT: "${PROJECT_ID}"
COOKIE_SECURE: "true"
DB_AUTO_CREATE: "false"
SCHEDULER_ENABLED: "false"
MEDIA_BACKEND: gcs
GCS_BUCKET: "${BUCKET}"
WEB_URL: "${WEB_URL}"
API_PUBLIC_URL: "${API_PUBLIC_URL}"
CORS_ORIGINS: '["${WEB_URL}"]'
TRUSTED_PROXY_HOPS: "${TRUSTED_PROXY_HOPS:-2}"
LANGSMITH_TRACING: "${TRACING}"
LANGSMITH_PROJECT: "${LANGSMITH_PROJECT}"
LINKEDIN_CLIENT_ID: "${LINKEDIN_CLIENT_ID:-}"
X_CLIENT_ID: "${X_CLIENT_ID:-}"
THREADS_APP_ID: "${THREADS_APP_ID:-}"
INSTAGRAM_APP_ID: "${INSTAGRAM_APP_ID:-}"
EOF
# --timeout 3600: AI runs stream for minutes. --concurrency 40: requests mostly wait on Gemini, so one
# instance serves many. CPU is only billed during requests; the scheduler below wakes it every minute.
gc run deploy "$SERVICE" --region "$REGION" --image "$IMAGE" --service-account "$SA" \
  --allow-unauthenticated --port 8080 --timeout 3600 --concurrency 40 --cpu 1 --memory 1Gi \
  --min-instances 0 --max-instances "$MAX_INSTANCES" --cpu-boost \
  --env-vars-file "$ENV_FILE" --set-secrets "$SECRETS" ${SQL_FLAGS[@]+"${SQL_FLAGS[@]}"}
API_URL="$(gc run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"

step "Cloud Scheduler: POST ${API_URL}/internal/tick every minute"
CRON="$(gc secrets versions access latest --secret brandbot-cron-secret)"
JOB_FLAGS=(--location "$REGION" --schedule "* * * * *" --uri "${API_URL}/internal/tick" --http-method POST
  --attempt-deadline 300s)
if gc scheduler jobs describe brandbot-tick --location "$REGION" >/dev/null 2>&1; then
  gc scheduler jobs update http brandbot-tick "${JOB_FLAGS[@]}" --update-headers "Authorization=Bearer ${CRON}"
else
  gc scheduler jobs create http brandbot-tick "${JOB_FLAGS[@]}" --headers "Authorization=Bearer ${CRON}"
fi

step "Checking ${API_URL}/ready"
curl -fsS "${API_URL}/ready" && echo

cat <<EOF

Done. Next:
  1. Web app on Vercel: project root "frontend", environment variable API_ORIGIN=${API_URL}, then redeploy.
  2. Platform developer apps: set each callback URL to ${API_PUBLIC_URL}/connections/<platform>/callback
     (platform = linkedin | x | threads | instagram).
EOF
