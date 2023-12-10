# BlaulichtSMS Homeassistant Component

## Development

```bash
python -m venv .
source bin/activate
pip install -r requirements.txt
```

Start a home assistant instance on your machine:

```bash
docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -e TZ=Europe/Vienna \
  -v $PWD/config:/config \
  -v /run/dbus:/run/dbus:ro \
  -p 8123:8123 \
  ghcr.io/home-assistant/home-assistant:stable
rsync -avz custom_components/blaulichtsms/ config/custom_components/blaulichtsms/;
docker restart homeassistant; docker logs -f homeassistant
```
