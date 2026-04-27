#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Building Frontend (React)..."
cd frontend
npm install
npm run build
cd ..

echo "Installing Backend dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt