#!/bin/bash
sudo docker run -d \
  --name=unifi-controller \
  -e PUID=1000 \
  -e PGID=1000 \
  -v /home/aau/unifi/:/config/ \
  --network=host \
  --restart unless-stopped \
  jacobalberty/unifi:latest
