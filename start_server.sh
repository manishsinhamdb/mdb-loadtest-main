#!/bin/bash
cd "/Users/manishsinha/Documents/00_projects/mdb-loadtest-main"
source venv/bin/activate
export LOADGEN_ENCRYPTION_KEY="5VBEwvTpmB61sH4CDpLHaWzev-ZcwHtXf8WEbTbGBYk="
uvicorn app:app --host 127.0.0.1 --port 8001
