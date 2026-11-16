#!/bin/bash
# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE in the project root for terms.


# Exit on error
set -e

echo "🚀 Starting deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one based on .env.example"
    exit 1
fi

echo "Git pulling latest changes..."
git pull origin Dev

echo "📦 Building and starting containers..."
docker compose up -d --build

echo "🧹 Cleaning up docker..."
docker system prune -a -f

echo "✅ Deployment successful!"

# sed -i 's/\r$//' deploy.sh
# To make the script executable, run: chmod +x deploy.sh
# To run the script, run: bash deploy.sh