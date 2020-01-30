#!/bin/bash

MAPFILE=${1-tmp/ip_mapping.txt}
INTERVAL=${2-2}

mkdir -p $(dirname $MAPFILE)
while true; do
		docker ps -q | xargs -n 1 docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}} {{ .Name }}' | sed 's/ \// /' > $MAPFILE
		sleep $INTERVAL
done
