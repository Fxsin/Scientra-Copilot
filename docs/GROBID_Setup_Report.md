# GROBID Setup Report

Generated at: 2026-06-08

## Executive Summary

GROBID Server has been installed and verified through Docker with image `grobid/grobid:0.9.0-crf`.

Current verified service:

- Host URL: `http://localhost:18070`
- Health endpoint: `http://localhost:18070/api/isalive`
- Health result: `200 true`
- Version endpoint: `http://localhost:18070/api/version`
- Version result: `{"version":"0.9.0","revision":"0.9.0"}`

Required Scientra Copilot URL:

- Target URL: `http://localhost:8070/api/isalive`
- Current result: failed, host cannot connect
- Root cause: Windows has reserved/excluded TCP port range `7991-8090`, which includes `8070`
- Required fix: run an elevated Administrator shell and remove or change the excluded port range, then restart the GROBID container with `-p 8070:8070`

## Check Results

| Check | Result |
|---|---|
| Host Java | `java version "1.8.0_481"` |
| Container Java | `OpenJDK 21.0.10 LTS` |
| Docker CLI | `Docker version 27.4.0, build bde2b89` |
| Docker Desktop backend | running after startup |
| Docker Desktop | `4.37.1 (178610)` |
| Docker Engine | `27.4.0` |
| GROBID Docker image | `grobid/grobid:0.9.0-crf` |
| GROBID version | `0.9.0` |
| Container name | `scientra_grobid` |
| Current host port | `18070 -> container 8070` |
| Current admin port | `18071 -> container 8071` |
| Required host port | `8070`, currently blocked by Windows port exclusion |

## Java Status

Host Java:

```powershell
java -version
```

Observed:

```text
java version "1.8.0_481"
Java(TM) SE Runtime Environment (build 1.8.0_481-b10)
Java HotSpot(TM) 64-Bit Server VM (build 25.481-b10, mixed mode)
```

This host Java version is not suitable as the primary path for current GROBID. The Docker image bundles its own Java runtime, so Scientra Copilot should use Docker-based GROBID unless a separate modern JDK is installed.

Container Java:

```powershell
docker exec scientra_grobid sh -lc "java -version"
```

Observed:

```text
openjdk version "21.0.10" 2026-01-20 LTS
OpenJDK Runtime Environment Temurin-21.0.10+7
OpenJDK 64-Bit Server VM Temurin-21.0.10+7
```

## Docker Status

Docker was installed but the Docker Desktop backend was initially stopped. It was started with:

```powershell
Start-Process -FilePath "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
```

Verification command:

```powershell
docker version
docker info
```

Observed:

```text
Docker CLI: 27.4.0
Docker Desktop: 4.37.1 (178610)
Docker Engine: 27.4.0
Backend OS: linux / WSL2
```

## GROBID Version

Docker image pulled:

```powershell
docker pull grobid/grobid:0.9.0-crf
```

Image inspection:

```powershell
docker image inspect grobid/grobid:0.9.0-crf
```

Observed:

```text
Image ID: sha256:68e60d9c6b74d9b5c5fc175db080aeb5466218c2055c757b746a43fa7b41f244
Created: 2026-04-07T16:00:09Z
Size: 1174982710 bytes
```

GROBID API version:

```powershell
Invoke-WebRequest -Uri "http://localhost:18070/api/version" -UseBasicParsing
```

Observed:

```json
{"version":"0.9.0","revision":"0.9.0"}
```

## Service Address And Port

Current working address:

```text
http://localhost:18070
```

Current health endpoint:

```text
http://localhost:18070/api/isalive
```

Required Scientra Copilot address:

```text
http://localhost:8070
```

Required Scientra Copilot health endpoint:

```text
http://localhost:8070/api/isalive
```

The required endpoint is not available yet because Windows currently blocks binding to port `8070`.

## Health Interface

Successful container-internal health check:

```powershell
docker exec scientra_grobid sh -lc "wget -qO- http://localhost:8070/api/isalive"
```

Result:

```text
true
```

Successful host health check on temporary port:

```powershell
Invoke-WebRequest -Uri "http://localhost:18070/api/isalive" -UseBasicParsing
```

Result:

```text
StatusCode: 200
Content: true
```

Failed required host health check:

```powershell
Invoke-WebRequest -Uri "http://localhost:8070/api/isalive" -UseBasicParsing
```

Result:

```text
Unable to connect to the remote server.
```

## Startup Commands

Current working startup command on temporary host port:

```powershell
docker rm -f scientra_grobid
docker run -d `
  --name scientra_grobid `
  --restart unless-stopped `
  --init `
  --ulimit core=0 `
  -p 18070:8070 `
  -p 18071:8071 `
  grobid/grobid:0.9.0-crf
```

Target startup command after fixing Windows port `8070`:

```powershell
docker rm -f scientra_grobid
docker run -d `
  --name scientra_grobid `
  --restart unless-stopped `
  --init `
  --ulimit core=0 `
  -p 8070:8070 `
  -p 8071:8071 `
  grobid/grobid:0.9.0-crf
```

Daily start/stop commands:

```powershell
docker start scientra_grobid
docker stop scientra_grobid
docker logs -f scientra_grobid
```

## Test Commands

Current working tests:

```powershell
Invoke-WebRequest -Uri "http://localhost:18070/api/isalive" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:18070/api/version" -UseBasicParsing
```

Pure Python health test:

```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:18070/api/isalive', timeout=10).read().decode())"
```

Required tests after port repair:

```powershell
Invoke-WebRequest -Uri "http://localhost:8070/api/isalive" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8070/api/version" -UseBasicParsing
```

Python test:

```powershell
python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://localhost:8070/api/isalive", timeout=10).read().decode())
print(urllib.request.urlopen("http://localhost:8070/api/version", timeout=10).read().decode())
PY
```

Scientra Copilot PDF Engine test:

```powershell
python -B Scripts/pdf_parser.py --check-grobid --grobid-url "http://localhost:8070"
```

Temporary port test before port repair:

```powershell
python -B Scripts/pdf_parser.py --check-grobid --grobid-url "http://localhost:18070"
```

Important: in the current `pdf_parser.py` implementation, `--check-grobid` verifies reachability but then continues into PDF processing. Do not use this command against production inputs as a pure health check until the CLI is patched to exit immediately after the GROBID check.

Safe Scientra-Copilot-level health check through the existing client:

```powershell
python -c "import sys; sys.path.insert(0, 'G:/AI_agent/Scientra Copilot/Scripts'); from grobid_client import GrobidClient; print(GrobidClient('http://localhost:18070', timeout_seconds=5, retries=0).is_alive())"
```

## Fault Cause

Port `8070` is inside a Windows excluded TCP port range.

Observed command:

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
netsh interface ipv6 show excludedportrange protocol=tcp
```

Observed blocked ranges include:

```text
7991        8090
8091        8190
```

Because `8070` is inside `7991-8090`, Docker cannot publish the port:

```text
Ports are not available: exposing port TCP 0.0.0.0:8070
listen tcp 0.0.0.0:8070: bind: An attempt was made to access a socket in a way forbidden by its access permissions.
```

Attempted repair in a non-elevated shell:

```powershell
netsh interface ipv4 delete excludedportrange protocol=tcp startport=7991 numberofports=100
```

Result:

```text
The requested operation requires elevation (Run as administrator).
```

## Repair Plan

Open Windows Terminal or PowerShell as Administrator.

Stop the current temporary container:

```powershell
docker stop scientra_grobid
docker rm scientra_grobid
```

Remove the excluded port range that contains `8070`:

```powershell
netsh interface ipv4 delete excludedportrange protocol=tcp startport=7991 numberofports=100
netsh interface ipv6 delete excludedportrange protocol=tcp startport=7991 numberofports=100
```

If Windows reports the range cannot be deleted because it is managed by Hyper-V, WSL, or WinNAT, restart the networking stack from an Administrator shell:

```powershell
net stop winnat
netsh interface ipv4 delete excludedportrange protocol=tcp startport=7991 numberofports=100
netsh interface ipv6 delete excludedportrange protocol=tcp startport=7991 numberofports=100
net start winnat
```

Start GROBID on the required Scientra Copilot port immediately after the blocking range is removed:

```powershell
docker run -d `
  --name scientra_grobid `
  --restart unless-stopped `
  --init `
  --ulimit core=0 `
  -p 8070:8070 `
  -p 8071:8071 `
  grobid/grobid:0.9.0-crf
```

Verify:

```powershell
Invoke-WebRequest -Uri "http://localhost:8070/api/isalive" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8070/api/version" -UseBasicParsing
python -B Scripts/pdf_parser.py --check-grobid --grobid-url "http://localhost:8070"
```

Expected final result:

```text
http://localhost:8070/api/isalive -> 200 true
http://localhost:8070/api/version -> {"version":"0.9.0","revision":"0.9.0"}
```

If Windows re-creates the `7991-8090` exclusion after reboot, repeat the Administrator repair before starting the GROBID container, or keep the temporary host port `18070` and configure the PDF Engine with `--grobid-url "http://localhost:18070"` until the machine-level port policy is changed.

## Scientra Copilot Configuration

Temporary configuration while `8070` is blocked:

```powershell
python -B Scripts/pdf_parser.py --check-grobid --grobid-url "http://localhost:18070"
```

Final configuration after repair:

```powershell
python -B Scripts/pdf_parser.py --check-grobid --grobid-url "http://localhost:8070"
```

The final target for Scientra Copilot remains:

```text
http://localhost:8070/api/isalive
```

## References

- GROBID Docker documentation: https://grobid.readthedocs.io/en/latest/Grobid-docker/
- GROBID REST API documentation: https://grobid.readthedocs.io/en/latest/Grobid-service/

## Final Status

GROBID itself is installed and running correctly in Docker.

The current host cannot expose GROBID at `http://localhost:8070` from a non-elevated shell because Windows has reserved the port range containing `8070`.

Until an Administrator shell removes or changes the excluded range, use:

```text
http://localhost:18070/api/isalive
```

After the Administrator repair, restart the container with the target command above and verify:

```text
http://localhost:8070/api/isalive
```
