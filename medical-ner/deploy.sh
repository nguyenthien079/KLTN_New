#!/usr/bin/env bash
# deploy.sh — Deploy Medical NER lên VPS Linux qua SSH + PEM key
# Cách dùng: ./deploy.sh <pem_key_path> <user@server_ip>
# Ví dụ:     ./deploy.sh ~/.ssh/mykey.pem ubuntu@123.45.67.89

set -e

PEM_KEY="$1"
SERVER="$2"
REMOTE_DIR="/opt/medical-ner"

if [[ -z "$PEM_KEY" || -z "$SERVER" ]]; then
  echo "Usage: ./deploy.sh <path/to/key.pem> <user@server_ip>"
  exit 1
fi

SSH="ssh -i \"$PEM_KEY\" -o StrictHostKeyChecking=accept-new \"$SERVER\""
SCP="scp -i \"$PEM_KEY\" -o StrictHostKeyChecking=accept-new"

echo "=== [1/4] Uploading project files ==="
rsync -az --delete \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'backend/data/*.db' \
  -e "ssh -i \"$PEM_KEY\" -o StrictHostKeyChecking=accept-new" \
  ./ "$SERVER:$REMOTE_DIR/"

echo "=== [2/4] Setting up server dependencies ==="
$SSH "
  cd $REMOTE_DIR
  if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker \$USER
    echo 'Docker installed.'
  fi
  if ! docker compose version &>/dev/null; then
    sudo apt-get install -y docker-compose-plugin
  fi
"

echo "=== [3/4] Building and starting containers ==="
$SSH "
  cd $REMOTE_DIR
  sudo docker compose down --remove-orphans || true
  sudo docker compose build --no-cache
  sudo docker compose up -d
"

echo "=== [4/4] Health check ==="
sleep 8
$SSH "curl -sf http://localhost:8000/api/health && echo 'Backend OK'" || echo "Backend chưa sẵn sàng, chờ thêm..."
$SSH "curl -sf http://localhost:80 > /dev/null && echo 'Frontend OK'" || echo "Frontend chưa sẵn sàng."

echo ""
echo "Deploy xong!"
echo "Truy cập: http://$(echo $SERVER | cut -d@ -f2)"
