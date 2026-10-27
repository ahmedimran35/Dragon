# Self-hosting

Dragon is one container with one volume. This page covers running it on a server, putting
HTTPS in front of it, and keeping your data safe.

## Docker Compose

```bash
cp .env.example .env && $EDITOR .env     # model key, DRAGON_SERVER_TOKEN, ...
docker compose up -d
docker compose logs -f                   # the access URL is printed once
```

By default the port is published on `127.0.0.1:8787` only. The compose file has a
comment showing how to publish it on your LAN instead.

Build the image yourself with `docker build -t dragon .`; add `--build-arg WITH_BROWSER=1`
for an image with Chromium and the browser tool ready (`dragon:browser` by convention).

## Reverse proxy with HTTPS

Keep the compose port on `127.0.0.1` and let a proxy own the public address. The web app
is a normal SPA + API + WebSocket, so any proxy works.

### Caddy

```
ember.example.com {
    reverse_proxy 127.0.0.1:8787
}
```

Caddy gets a certificate and renews it automatically.

### Traefik (labels on the service)

```yaml
services:
  dragon:
    # ... as in docker-compose.yml, ports: ["127.0.0.1:8787:8787"] stays
    labels:
      - traefik.enable=true
      - traefik.http.routers.dragon.rule=Host(`ember.example.com`)
      - traefik.http.routers.dragon.entrypoints=websecure
      - traefik.http.routers.dragon.tls.certresolver=le
      - traefik.http.services.dragon.loadbalancer.server.port=8787
```

WebSocket upgrade needs no special configuration in either proxy.

**Exposure rules of thumb**

- Never publish `8787` on a public interface; the token is a bearer secret in a URL.
- Use HTTPS: the token travels in the URL fragment and in headers.
- If you want a second layer, add HTTP basic auth at the proxy.

## The token

First run generates the token into `<data_dir>/server_token` and prints it once in the
`#token=…` link (also as a QR code in the app). To rotate: stop the container, delete the
file (or set `DRAGON_SERVER_TOKEN` in `.env`), start again. Details in
[security.md](security.md).

## Backups

All state is in `/data` (the `dragon-data` volume): memory, goals, reminders, the vault,
the audit log, sessions, `app-settings.json`, `server_token`.

```bash
# while running (the data is plain files + SQLite; a copy is fine)
docker run --rm -v dragon-data:/data -v "$PWD":/out alpine \
  tar czf /out/dragon-backup-$(date +%F).tar.gz -C /data .
```

Also back up:

- `./workspace` (or whatever `DRAGON_WORKSPACE` points at) — the agent's files;
- **the vault key** (`/data/vault.key`, or `DRAGON_VAULT_KEY` if you set one) — without it
  the vault cannot be opened and every stored key is lost. Keep it somewhere else than
  the backup tarball if you can.

## Restore

```bash
docker compose down
docker run --rm -v dragon-data:/data -v "$PWD":/out alpine \
  tar xzf /out/dragon-backup-2026-10-27.tar.gz -C /data
docker compose up -d
```

## Upgrades

```bash
docker compose build --pull    # or: docker compose pull, for a published image
docker compose up -d
```

Back up first. Check [CHANGELOG.md](../CHANGELOG.md) for anything that changes the config
format; `dragon doctor` after an upgrade catches the common mistakes.

## Also worth knowing

- **`dragon daemon`** keeps goals and triggers advancing with no browser open —
  `docker compose run -d dragon dragon daemon` or a systemd unit.
- **`dragon doctor`** validates the config, the model connection, the vault and the
  sandbox; run it after every move to a new machine.
- **Data directory on a new disk**: stop Dragon, move `/data`, point `DRAGON_DATA_DIR` (or
  the volume) at the new place, start.
- **One user, one runtime.** Running two containers on the same volume will corrupt it.
