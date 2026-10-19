#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files for Django admin/rest_framework
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Provision or synchronize administrator account from Render environment variables
python manage.py bootstrap_admin
