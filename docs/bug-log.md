# Bug Log

| # | Date | What broke | Cause | Fix |
|---|------|-----------|-------|-----|
| 1 | 2026-10-18 | `go install` failed with `errno.h: No such file` | Missing C build tools in fresh Ubuntu | `sudo apt install build-essential` |
| 2 | 2026-10-18 | `No module named 'app'` | Ran command from project root instead of `backend/` | `cd backend` before running |
| 3 | 2026-10-21 | Sunday's work showed as untracked in `git status` | Never committed it | Committed in logical pieces |
| 4 | 2026-10-21 | pytest reported `collected 0 items` | Test file had not been created yet | Created `tests/test_validators.py` |
| 5 | 2026-10-21 | Frontend text invisible | Next.js template switches to a dark background in OS dark mode, but the page used dark text | Locked `globals.css` to a light theme |
| 6 | 2026-10-26 | Plain `pytest` failed in every test file with `No module named 'app'` | Plain `pytest` does not add `backend/` to the import path; `python -m pytest` does | Added `backend/pytest.ini` with `pythonpath = .` and use `python -m pytest` |
| 7 | 2026-10-26 | Update zip would not apply | `unzip` was not installed; a pasted command block ran `rm` on the zip before the unzip had worked; later the unzip ran in the wrong folder | Installed unzip, copied the zip again, ran the commands one at a time from `~/recon-platform` |
| 8 | 2026-10-26 | A scan stayed on "Waiting to start" | Celery was not initialized properly | Interface hint after about 15 seconds; Stop scan works on queued scans; worker skips stopped scans |
| 9 | 2026-10-26 | Certificate warning showed no reason ("failed:") | The error carried no message text and only that text was printed | Added readable error reasons (`describe_error`) |
| 10 | 2026-10-26 | Certificate lookup failed with HTTP 404, so scans found fewer hosts | One public source (crt.sh) with no retry | Retry with a growing pause and a Cert Spotter fallback; HTML error pages count as failures. Verified on a later scan |
| 11 | 2026-10-26 | Design gap: any scan could be fetched by its ID and cached scans would be shared | Scans had no owner (single-user prototype) | Added accounts, an owner on every scan, owner-filtered queries and 404 for other users' IDs; 10 isolation tests |
| 12 | 2026-10-29 | `python: command not found` when running the benchmark | Virtual environment not active, and the placeholder domain was left in the command | `source venv/bin/activate` and a real domain |
| 13 | 2026-11-05 | No sign that a host row can be expanded | Rows were clickable but gave no visual cue | Added an expand indicator to the host table |
