#!/bin/sh
set -eu

if [ -f .env ] && [ -s .env ]; then
  echo ".env already exists, keeping current file."
  exit 0
fi

cat > .env <<'EOF'
SECRET_KEY="${SECRET_KEY:-}"
DEBUG="${DEBUG:-True}"
DATABASE_URL="${DATABASE_URL:-}"
SUPABASE_URL="${SUPABASE_URL:-}"
SUPABASE_KEY="${SUPABASE_KEY:-}"
DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-no-reply@bioattend.local}"
BREVO_API_KEY="${BREVO_API_KEY:-}"
BREVO_SENDER_EMAIL="${BREVO_SENDER_EMAIL:-${DEFAULT_FROM_EMAIL:-no-reply@bioattend.local}}"
BREVO_SENDER_NAME="${BREVO_SENDER_NAME:-BioAttend}"
BREVO_API_ENDPOINT="${BREVO_API_ENDPOINT:-https://api.brevo.com/v3/smtp/email}"
EOF

echo ".env generated from environment variables."
