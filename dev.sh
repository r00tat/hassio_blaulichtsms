#!/bin/bash
# setup dev environemnt
set -eo pipefail

if [[ -z "$(which uv)" ]]; then
  echo "uv required!"
  echo "see https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  uv venv
  source .venv/bin/activate
  uv pip install -r requirements.txt
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
