# Running CODE_AGENT in production

One virtual machine, Docker, Caddy in front for the domain and HTTPS. This guide takes a fresh
Ubuntu VM to a public site, then covers backups, restores, monitoring and upgrades.

## Single instance, by design

The job queue, rate limits, sandbox slots and the Chroma memory store all live in one process,
and the server takes a lock on its data folder so a second copy can't start on the same data.
Run **exactly one** stack per data volume. A bigger VM goes a long way (each run mostly waits on
Groq and Docker). Scaling out would need a shared queue and Postgres, which this project doesn't do.

## 1. The machine

- Ubuntu 24.04 LTS (or any Linux with Docker), 2 vCPUs and 4 GB RAM to start, 20 GB+ disk.
- A dedicated VM: whoever can start containers on a host is close to root on it, and the
  sandbox shares the host kernel. Don't run other important things beside it.
- A domain name with an `A` (and `AAAA` if you have IPv6) record pointing at the VM.

```bash
# Docker Engine + the compose plugin (from Docker's own instructions)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Firewall: SSH and the web only. The app itself listens on 127.0.0.1 and isn't exposed.
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
```

## 2. Configure

```bash
git clone https://github.com/FarhanAaqil/self-improving-agent.git && cd self-improving-agent
cp .env.example .env
```

Edit `.env`. These matter in production:

| Setting | Value |
|---|---|
| `APP_ENV` | `production` (also the default when unset) |
| `DOMAIN` | `your-domain.example` |
| `PUBLIC_BASE_URL` | `https://your-domain.example` (links in emails) |
| `API_KEY` | a long random string: `openssl rand -hex 32`. Your operator key |
| `ADMIN_EMAILS` | your own email, for the admin page in the browser |
| `GROQ_API_KEY` | the server key Pro accounts use (Free accounts bring their own) |
| `SMTP_*`, `MAIL_FROM` | an SMTP provider, so people can confirm their email and reset passwords |
| `CERT_SIGNING_KEY` | `openssl rand -hex 32`, signs exported certificates |
| `PAYMENT_LINK_URL` | your payment link (optional) |
| `SENTRY_DSN` | error tracking (optional) |
| `ALLOW_UNSAFE_HOST_SUBPROCESS`, `ALLOW_CODE_OVERRIDE` | leave `false`: production refuses to start otherwise |

## 3. Start

```bash
docker pull python:3.11-slim              # the image sandboxed code runs in
docker compose -f docker-compose.yml -f deploy/docker-compose.caddy.yml up -d --build
docker compose logs -f api                # JSON logs; Ctrl+C to stop following
```

Caddy gets a certificate on first request. Open `https://your-domain.example`: the landing page
with the live demo. Sign up with the address in `ADMIN_EMAILS` and the **admin** link appears.

The server refuses to boot (and says why in the logs) if Docker can't be reached, or if either of the
two unsafe switches is on.

## 4. Backups

The server writes `backup-YYYYmmdd-HHMMSS.tar.gz` to `BACKUP_DIR` (default `/data/backups`
inside the data volume) every `BACKUP_EVERY_HOURS` (24), keeping the newest `BACKUP_KEEP` (14).
Each archive holds a consistent copy of the SQLite database (taken with SQLite's online backup API
while the app runs) and of the Chroma memory folder (copied while memory writes are paused), plus
a manifest with row and memory counts. The admin page has **back up now**, or:

```bash
curl -X POST -H "X-API-Key: $API_KEY" https://your-domain.example/admin/backup
```

**Copy backups off the machine**; a backup on the same disk dies with it. For example, nightly
with cron on the VM:

```bash
# /etc/cron.d/agent-backups: 04:15 every night, after the server's own backup
15 4 * * * root cd /home/ubuntu/self-improving-agent && \
  docker compose cp api:/data/backups ./backups-copy && \
  rclone sync ./backups-copy remote:agent-backups --max-age 15d
```

### Restore test (run it now and then)

```bash
docker compose exec api python -m app.backup verify /data/backups/$(docker compose exec api ls /data/backups | tail -1)
```

It unpacks the archive into a temporary folder, runs SQLite's integrity check, and checks that the
row counts and the memory count match what the backup recorded. `Restore test passed.` means the
archive is good.

### Restoring on a fresh machine

1. Set up the new VM with steps 1–2 (same `.env`).
2. Build without starting: `docker compose -f docker-compose.yml -f deploy/docker-compose.caddy.yml build`.
3. Put the archive in the data volume and restore while the API is stopped:

```bash
docker compose run --rm -v "$PWD/backups-copy:/restore:ro" api \
  python -m app.backup restore /restore/backup-YYYYmmdd-HHMMSS.tar.gz
```

4. Start the stack (step 3) and point DNS at the new machine.

`restore` checks the archive first, refuses if a server holds the data lock, and moves any existing
data aside (`*.before-restore-<time>`) instead of deleting it (`--force` is needed if the target
already has runs).

## 5. Monitoring

- **Uptime**: set the repository variable `PUBLIC_URL` (GitHub: Settings → Secrets and variables →
  Actions → Variables) to `https://your-domain.example`. The `Uptime` workflow checks `/health`
  every 10 minutes, and GitHub emails you when it fails. Any external monitor (UptimeRobot,
  Better Stack…) pointed at `/health` works too.
- **Errors**: set `SENTRY_DSN`. Reports carry the account id and request id only: no request
  bodies, cookies, auth headers, Groq keys, query strings or local variables.
- **Logs**: one JSON line per request with `request_id`, `user_id`, the route template, status
  and duration. Never keys, passwords or submitted code. `docker compose logs api`.
- **Metrics**: `GET /metrics` (operator key) in Prometheus format.

## 6. Abuse controls

- Accounts younger than 24 hours get a lower runs-per-day cap and a tighter per-minute limit.
- Free accounts can only spend their own Groq key; Pro accounts have a daily budget on yours.
- The admin page lists every account with plan and today's usage, and has a **disable** switch:
  the account is signed out everywhere and its API keys stop working.
- `SIGNUPS_OPEN=false` closes sign-ups in an emergency; `DEMO_ENABLED=false` turns off the demo.

## 7. Upgrades

```bash
git pull
docker compose -f docker-compose.yml -f deploy/docker-compose.caddy.yml up -d --build
```

Take a backup first (admin page or the curl above). Database changes are applied automatically
on start-up and only ever add columns and tables.

## 8. Before launch

- Have a lawyer review the **draft** Terms, Privacy and Acceptable Use pages (`/terms`,
  `/privacy`, `/acceptable-use`); they are marked as drafts on purpose.
- Send yourself a sign-up email and a password reset to check SMTP.
- Run the restore test on a real backup.
