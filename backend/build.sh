#!/usr/bin/env bash
# Comando de build en Render (Dashboard -> Settings -> Build Command:
# ./build.sh). Se corre en cada deploy, antes de arrancar el servicio.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser --noinput || true