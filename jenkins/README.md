# jenkins

Local Jenkins for openproject-mcp. Runs in Docker on your laptop. JCasC
provisions everything (admin user, matrix auth, the multibranch pipeline)
so there's no first-boot wizard to click through.

## prerequisites

- Docker Desktop (or compatible engine) running
- the rest of the monorepo checked out (we mount `jenkins_home` as a named
  volume - code lives in the running container, not bind-mounted from host)

## setup

```bash
cd jenkins
cp .env.example .env       # admin id/password for first boot (gitignored)
docker compose up -d --build
```

Wait ~60s for Jenkins to come up, then open `http://localhost:8080`. Log in
with whatever you put in `.env` (defaults: `admin` / `password`).

## what's inside

- `Dockerfile` - `jenkins/jenkins:2.452.3-lts-jdk17`, JCasC + Job DSL plugins
  installed at build time
- `plugins.txt` - pinned plugin set (configuration-as-code, job-dsl,
  docker-workflow, kubernetes, etc.)
- `casc.yaml` - admin user (read from `${JENKINS_ADMIN_*}` env), Matrix
  Authorization, remoting security enabled
- `jobs/openproject-mcp.groovy` - multibranch pipeline pointing at this
  repo's root `Jenkinsfile`
- `docker-compose.yml` - Jenkins + a `docker:dind` sidecar so the pipeline
  can run `docker buildx` without mounting the host docker socket

## troubleshooting

**Setup wizard keeps showing up.** Means JCasC isn't loading. Check
`CASC_JENKINS_CONFIG` is set in the Dockerfile and that `casc.yaml` actually
got copied to `/var/jenkins_home/casc.yaml`. If you mount `jenkins_home`
from a previous run, the wizard-completed marker file may be stale - wipe
the volume: `docker compose down -v && docker compose up -d --build`.

**`docker buildx` stage fails with "docker: command not found".** The
jenkins container talks to the dind sidecar over `tcp://dind:2375`
(`DOCKER_HOST` env). If `docker compose ps` shows dind exited, check the
dind logs - usually it's `privileged: true` getting denied by the host.

**`mcp-builder` builder not found on fresh runs.** Expected - buildx
builders live in the dind volume which gets reset whenever you wipe the
named volume. The Jenkinsfile `Setup buildx` stage does
`docker buildx inspect mcp-builder || docker buildx create --name mcp-builder --use`
so it self-heals.

**Pipeline can't find `dockerhub-token` credential.** First-time setup,
the credential doesn't exist yet. Add it from Manage Jenkins → Credentials
→ System → Global. Username = Docker Hub username (`gsst3ja`), password =
PAT with `Read, Write, Delete` scope. ID must be exactly
`dockerhub-token` (referenced by the Jenkinsfile).

## what's not here yet

- AWS / EKS deploy stages - placeholder steps in the Jenkinsfile that echo
  "not ready yet". Real deploy lands when terraform/helm catch up.
- Real GitHub remote - `jobs/openproject-mcp.groovy` has a TODO for the
  org/repo. Set it once we `gh repo create`.
