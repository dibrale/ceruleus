#! /bin/bash
echo 'Starting Ceruleus server in background'
python main.py 3>&1 1>>logfile.log 2>&1 &
echo "Log file path: $(pwd)/logfile.log"
echo "PID: $!"
echo 'Starting Ceruleus client'
python ceruleus_client.py