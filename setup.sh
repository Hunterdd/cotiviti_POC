#!/usr/bin/env bash
# setup.sh — one-command environment setup
set -e

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt

echo ""
echo "✅ Setup complete."
echo ""
echo "Next steps:"
echo "  1. cp .env.example .env"
echo "  2. Edit .env and add your OPENROUTER_API_KEY"
echo "  3. source .venv/bin/activate"
echo "  4. streamlit run app.py"
