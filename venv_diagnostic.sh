#!/bin/bash
# Virtual Environment Diagnostic Script
# Run from project root: bash venv_diagnostic.sh

echo "=========================================="
echo "1. CHECK CURRENT PYTHON & VENV"
echo "=========================================="
echo "VIRTUAL_ENV: $VIRTUAL_ENV"
which python
python --version
echo ""

echo "=========================================="
echo "2. CHECK WHERE PIP IS INSTALLING"
echo "=========================================="
pip --version
python -c "import sys; print(f'Python executable: {sys.executable}')"
python -c "import sys; print(f'Site packages: {sys.path}')"
echo ""

echo "=========================================="
echo "3. CHECK IF dj-01 VENV EXISTS"
echo "=========================================="
if [ -d "$HOME/.venvs/dj-01" ]; then
    echo "✓ dj-01 virtualenv exists at: $HOME/.venvs/dj-01"
    ls -la "$HOME/.venvs/dj-01/bin/" | grep -E "(python|pip|activate)"
else
    echo "✗ dj-01 virtualenv NOT found at: $HOME/.venvs/dj-01"
    echo "Checking other common locations..."
    find "$HOME/.venvs" -maxdepth 1 -type d -name "*dj*" 2>/dev/null || echo "(no venvs found)"
fi
echo ""

echo "=========================================="
echo "4. CHECK SENTRY-SDK IN PYENV GLOBAL"
echo "=========================================="
/home/marcel/.pyenv/versions/3.12.6/bin/python -c "import sentry_sdk; print(f'✓ sentry-sdk {sentry_sdk.VERSION} in pyenv global')" 2>&1
echo ""

echo "=========================================="
echo "5. CHECK SENTRY-SDK IN dj-01 VENV"
echo "=========================================="
if [ -f "$HOME/.venvs/dj-01/bin/python" ]; then
    "$HOME/.venvs/dj-01/bin/python" -c "import sentry_sdk; print(f'✓ sentry-sdk {sentry_sdk.VERSION} in dj-01')" 2>&1 || echo "✗ sentry-sdk NOT installed in dj-01"
else
    echo "✗ dj-01 Python executable not found"
fi
echo ""

echo "=========================================="
echo "6. SOLUTION: ACTIVATE VENV & INSTALL"
echo "=========================================="
echo "Run these commands:"
echo ""
echo "  source ~/.venvs/dj-01/bin/activate"
echo "  cd /home/marcel/projects/statuswatch-project/backend"
echo "  pip install -r requirements.txt"
echo "  python manage.py runserver 0.0.0.0:8001"
echo ""
echo "Or if venv doesn't exist, create it:"
echo ""
echo "  python -m venv ~/.venvs/dj-01"
echo "  source ~/.venvs/dj-01/bin/activate"
echo "  cd /home/marcel/projects/statuswatch-project/backend"
echo "  pip install -r requirements.txt"
echo "  python manage.py runserver 0.0.0.0:8001"
echo ""
echo "=========================================="
