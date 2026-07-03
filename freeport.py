"""Print the first bindable TCP port at/above a start port (default 8000).

Used by deploy.sh / deploy.ps1 to pick a port that uvicorn can actually bind —
this skips ports already in use AND Windows "excluded port ranges" (which fail a
real bind with winerror 10013 / PermissionError), because we test with an actual
socket bind rather than just checking if something is listening.

Usage:  python freeport.py [start] [count]   -> prints the port, exit 0
        exit 1 if none found in [start, start+count).
"""
import socket
import sys

start = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
count = int(sys.argv[2]) if len(sys.argv) > 2 else 200
host = "127.0.0.1"

for port in range(start, start + count):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
        print(port)
        sys.exit(0)
    except OSError:
        s.close()
        continue

print(f"ERROR: no free port found in [{start}, {start + count})", file=sys.stderr)
sys.exit(1)
