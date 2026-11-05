# Dev Log

## 2026-10-18 (Sun)
- Built: tool installs, domain validator, subfinder/httpx wrappers
- Went wrong: go install failed (missing build tools); ran module from wrong folder

## 2026-10-21 (Wed)
- Sunday's code was only committed today (should have committed as I went)
- Added unit tests for domain validation
- Starting database, API, and Celery worker
- Committed the rest of the first version: SQLAlchemy models, Celery worker task, FastAPI scan endpoints, CORS, Next.js frontend, recon parsing and API tests, README
- Went wrong: frontend text was invisible in OS dark mode (bug 6)

## 2026-10-22 (Thu)
- Built: scan history endpoint and reuse of recent scans (within 24 hours)
- Asked the lecturer whether the problem and solution were suitable. Reply: "Implement something within and follow the SE process."
- Understood it as: the core engine must be my own code instead of a wrapper around Subfinder and HTTPx, and the project needs documented SE phases.
- Decided to rebuild the engine, add user accounts with per-user scan history, and add scan comparison.

## 2026-10-26 (Mon)
- Wrote the requirements for the new scope (FR1-FR11, NFR1-NFR6).
- Built my own engine: certificate transparency lookup (crt.sh), wordlist DNS brute force with a concurrency limit, wildcard DNS filtering, async HTTP prober, pipeline, and scan comparison (added, removed, changed). Moved Subfinder and HTTPx into optional adapters.
- Added accounts: register, login, logout, scrypt password hashing, server-side sessions, an owner on every scan, and isolation tests proving one user cannot read, list, compare or delete another user's scans.
- Built the new Next.js interface: login and register, scan history, sonar map, host table with filters, and a changes tab.
- Added Stop scan: API endpoint, worker skips scans stopped while queued, engine stops mid-scan.
- Went wrong: plain `pytest` could not import the app (bug 7); update zips applied in the wrong folder (bug 8); a scan stuck on "Waiting to start" (bug 9); the certificate lookup failed with an empty warning and then an HTTP 404 (bugs 10 and 11). Also found the design gap that any scan could be fetched by ID before accounts existed (bug 12).

## 2026-10-27 (Tue)
- Fixed the certificate lookup: retries with a growing pause, Cert Spotter as a fallback, readable error reasons.
- Added the hide/show history panel.
- Took screenshots, recorded the demo video, and rewrote the README.

## 2026-10-29 (Thur)
- Checked the problem against industry evidence after prototyping (unmanaged-asset studies, Communications Authority of Kenya figures, comparison with reNgine).
- Wrote the Part IV testing and QA report: 79 automated tests (36 unit, 43 integration), manual test cases, a performance benchmark, and a feedback session with two users.
- Ran the benchmark on cultbeauty.co.uk (3 runs): mean total 9.81 s, certificate lookup was the slowest stage, 10 hosts found each run. Earlier scans of the same domain, while the certificate lookup was failing, found 5.
- Full test run on my machine: 79 passed in 5.12 s.
- Went wrong: ran the benchmark with the virtual environment inactive and with the placeholder domain (bug 13).

## 2026-11-05 (Thu)
- Added an expand indicator to the host table so it is clear a row can be opened (bug 14).
- Rewrote the README setup steps and added a troubleshooting table.
