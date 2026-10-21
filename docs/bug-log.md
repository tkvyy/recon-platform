# Bug Log

| # | Date | What broke | Cause | Fix |
|---|------|-----------|-------|-----|
| 1 | 2026-10-18 | `go install` failed with `errno.h: No such file` | Missing C build tools in fresh Ubuntu | `sudo apt install build-essential` |
| 2 | 2026-10-18 | `No module named 'app'` | Ran command from project root instead of `backend/` | `cd backend` before running |
| 3 | 2026-10-21 | Sunday's work showed as untracked in `git status` | Never committed it | Committed in logical pieces |
| 4 | 2026-10-21 | pytest reported `collected 0 items` | Test file had not been created yet | Created `tests/test_validators.py` |
