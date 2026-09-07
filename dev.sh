#!/bin/bash
# Richtet die lokale Entwicklungsumgebung ein und startet eine Home-Assistant-
# Testinstanz im Container, in die die Komponente hineinsynchronisiert wird.
set -euo pipefail

COMPONENT="blaulichtsms"
DOCKER_NAME="homeassistant"
IMAGE="ghcr.io/home-assistant/home-assistant:stable"
# Host-Port. Im Container lauscht Home Assistant immer auf 8123 (Container-
# Installationen behalten diesen Default auch nach dem Wechsel auf Port 80,
# der nur neue Home-Assistant-OS-Installationen betrifft).
HTTP_PORT="${HTTP_PORT:-8123}"

RECREATE=0
FOLLOW_LOGS=1

usage() {
  cat <<EOF
Usage: $0 [--recreate] [--no-logs]

  --recreate   Container verwerfen und neu anlegen. Nötig, wenn sich Port,
               Image oder Mounts geändert haben.
  --no-logs    Nach dem Start nicht an den Container-Logs hängen.

Umgebungsvariablen:
  HTTP_PORT    Host-Port für die Weboberfläche (Default: 8123)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE=1 ;;
    --no-logs) FOLLOW_LOGS=0 ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unbekannte Option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

log() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '[!] %s\n' "$*" >&2; }

# --- Voraussetzungen ---------------------------------------------------------

log "Prüfe Voraussetzungen"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv wird benötigt!"
  warn "siehe https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi
info "uv: $(command -v uv)"

if ! docker info >/dev/null 2>&1; then
  warn "Docker ist nicht erreichbar — läuft der Daemon?"
  exit 1
fi
info "docker: erreichbar"

# --- Python-Umgebung ---------------------------------------------------------

if [[ ! -d ".venv" ]]; then
  log "Lege virtuelle Umgebung an (.venv)"
  uv venv
else
  log "Verwende bestehende virtuelle Umgebung (.venv)"
fi

# Bei jedem Lauf, damit Änderungen an requirements.txt nicht übersehen werden.
log "Installiere Python-Abhängigkeiten aus requirements.txt"
uv pip install --quiet -r requirements.txt
info "$(grep -c '^[^#[:space:]]' requirements.txt) Anforderungen aktuell"

# --- Komponente in die Testkonfiguration spiegeln ----------------------------

log "Synchronisiere custom_components/$COMPONENT nach config/"
mkdir -p "config/custom_components"
# --delete, damit im Repo gelöschte Dateien nicht als Leichen weiterleben und
# von Home Assistant geladen werden. Kein -z: rein lokale Kopie.
rsync -a --delete --exclude '__pycache__' \
  "custom_components/$COMPONENT/" "config/custom_components/$COMPONENT/"
info "$(find "config/custom_components/$COMPONENT" -name '*.py' | wc -l | tr -d ' ') Python-Dateien gespiegelt"

# --- Container ---------------------------------------------------------------

DOCKER_RUN_ARGS=(
  --name "$DOCKER_NAME"
  -e TZ=Europe/Vienna
  -v "$PWD/config:/config"
  # Nur lokal veröffentlichen — die Testinstanz muss nicht im LAN hängen.
  -p "127.0.0.1:$HTTP_PORT:8123"
)

# D-Bus und --privileged braucht Home Assistant nur für lokale Hardware
# (Bluetooth, USB) auf Linux-Hosts. Auf macOS/Windows existiert der Socket
# nicht, der Mount wäre ein leeres Verzeichnis.
if [[ -S /run/dbus/system_bus_socket ]]; then
  DOCKER_RUN_ARGS+=(--privileged -v /run/dbus:/run/dbus:ro)
  info "D-Bus-Socket gefunden — Hardwarezugriff aktiviert"
else
  info "kein D-Bus-Socket — ohne --privileged (Hardwarezugriff nicht nötig)"
fi

# Exakter Match: -f name=… ist sonst ein Teilstring-Vergleich.
container_id="$(docker ps -a -q -f "name=^${DOCKER_NAME}\$")"

# Portmapping, Image und Mounts liegen beim docker run fest und lassen sich
# per docker restart nicht ändern — Abweichung erkennen statt stillschweigend
# den alten Container weiterlaufen zu lassen.
if [[ -n "$container_id" && "$RECREATE" -eq 0 ]]; then
  # HostConfig.PortBindings, nicht NetworkSettings.Ports: letzteres ist bei
  # einem gestoppten Container leer und würde eine Änderung vortäuschen.
  current_port="$(docker inspect "$container_id" \
    --format '{{with index .HostConfig.PortBindings "8123/tcp"}}{{(index . 0).HostPort}}{{end}}')"
  if [[ "$current_port" != "$HTTP_PORT" ]]; then
    warn "Bestehender Container veröffentlicht Port ${current_port:-<keinen>}, gewünscht ist $HTTP_PORT."
    warn "Portmappings sind unveränderlich — Container wird neu angelegt."
    RECREATE=1
  fi
fi

if [[ -n "$container_id" && "$RECREATE" -eq 1 ]]; then
  log "Entferne bestehenden Container $DOCKER_NAME"
  # Erst geordnet stoppen, damit Home Assistant seine SQLite-Datenbank in
  # config/ sauber schließt; rm -f allein wäre ein SIGKILL.
  docker stop -t 30 "$DOCKER_NAME" >/dev/null 2>&1 || true
  docker rm -f "$DOCKER_NAME" >/dev/null
  container_id=""
fi

if [[ -z "$container_id" ]]; then
  log "Starte neuen Container $DOCKER_NAME"
  info "Image: $IMAGE"
  docker run -d "${DOCKER_RUN_ARGS[@]}" "$IMAGE" >/dev/null
else
  log "Starte bestehenden Container $DOCKER_NAME neu"
  docker restart "$DOCKER_NAME" >/dev/null
fi

log "Home Assistant startet — Weboberfläche: http://localhost:$HTTP_PORT"
info "Der erste Start dauert 20-30 s, bis die Oberfläche antwortet."
info "Komponente neu laden: ./dev.sh erneut ausführen (spiegelt + startet neu)."

if [[ "$FOLLOW_LOGS" -eq 1 ]]; then
  # Ctrl-C stoppt die Testinstanz, statt nur das Mitlesen zu beenden. Wer den
  # Container weiterlaufen lassen will, startet mit --no-logs.
  stop_container() {
    trap - INT TERM
    log "Stoppe Container $DOCKER_NAME"
    # Home Assistant braucht für ein sauberes Herunterfahren mehr als die 10 s
    # Kulanz, die docker stop standardmäßig vor dem SIGKILL gewährt.
    docker stop -t 30 "$DOCKER_NAME" >/dev/null
    info "Gestoppt. Neu starten: ./dev.sh"
    exit 0
  }
  trap stop_container INT TERM

  log "Container-Logs — Ctrl-C stoppt die Testinstanz"
  # Endet das Tailing von selbst, ist der Container weg oder abgestürzt.
  docker logs -n 10 -f "$DOCKER_NAME" || true
  trap - INT TERM
  warn "Log-Tailing beendet — Container läuft nicht mehr."
  docker ps -a -f "name=^${DOCKER_NAME}\$" --format '    {{.Names}}: {{.Status}}'
fi
