#!/bin/bash
# setup dev environemnt
set -eo pipefail

if [[ ! -d "bin" || ! -f "bin/activate" ]]; then
  python3 -m venv .
  source bin/activate
  pip3 install -r requirements.txt
fi

if [[ ! -d "config" ]]; then
  mkdir config
fi

rsync -avz custom_components/blaulichtsms/ config/custom_components/blaulichtsms/

if [ ! "$(docker ps -a -q -f name=homeassistant)" ]; then
  docker run -d \
    --name homeassistant \
    --privileged \
    --restart=unless-stopped \
    -e TZ=Europe/Vienna \
    -v $PWD/config:/config \
    -v /run/dbus:/run/dbus:ro \
    -p 8123:8123 \
    ghcr.io/home-assistant/home-assistant:stable

else
  docker restart homeassistant
fi
docker logs -n 10 -f homeassistant
