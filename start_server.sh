#!/bin/bash
cd "/Users/manishsinha/Documents/00_projects/mdb-loadtest-main"
source venv/bin/activate
export LOADGEN_ENCRYPTION_KEY="he0KzYwHtykl_GnYRGtwMNDDLftHKuXljg8TNvj9rBE="
uvicorn app:app --host 127.0.0.1 --port 8001
