#!/usr/bin/env bash

pip install -r requirements.txt

cd backend

python manage.py collectstatic --noinput

python manage.py migrate