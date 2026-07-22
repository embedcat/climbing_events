#!/bin/bash

cd ~/climbing_events

docker compose -f docker-compose.prod.yml exec -T web python manage.py check_close_registration
