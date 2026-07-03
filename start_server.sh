#!/bin/bash
cd "/Users/manishsinha/Documents/00_projects/mdb-loadtest-main"
source venv/bin/activate
export LOADGEN_ENCRYPTION_KEY="Zd7NzFx-8aHhgGlD8KXAbHmyhXV7J4qOorDZPwe07Qw="
uvicorn app:app --host 127.0.0.1 --port 8001
