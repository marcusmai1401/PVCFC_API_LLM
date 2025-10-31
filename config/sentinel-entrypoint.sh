#!/bin/sh
echo "Waiting for redis-master to be resolvable..."
i=1
while [ $i -le 60 ]; do
    if ping -c 1 redis-master > /dev/null 2>&1; then
        echo "redis-master resolved successfully!"
        exec redis-sentinel /etc/redis/sentinel.conf
    fi
    echo "Attempt $i/60: redis-master not yet resolvable, waiting..."
    sleep 1
    i=$((i+1))
done
echo "ERROR: redis-master could not be resolved after 60 seconds"
exit 1
