# Dependency update & audit process

## Files
- `requirements.in`: Source list of top-level dependencies.
- `requirements.txt`: Fully pinned production dependencies.
- `requirements-nodeps.txt`: Packages installed without their declared
  dependencies (currently only PyJHora).

## Installing
```bash
pip install -r requirements.txt
pip install --no-deps -r requirements-nodeps.txt
```

PyJHora 5.0.6 pins desktop UI packages (PyQt6) and older versions of `numpy`,
`pytz` and `timezonefinder`. The service does not need them, so `pip check` is
expected to report those requirements as unmet. When upgrading PyJHora, check
that its imports are covered by `requirements.in` and run the tests.

## Updating dependencies
1. Update `requirements.in` with the desired top-level packages.
2. If `pip-tools` is available, regenerate `requirements.txt` with hashes:
   ```bash
   python -m pip install --upgrade pip-tools
   pip-compile --generate-hashes --output-file requirements.txt requirements.in
   ```
3. Ensure pinned versions remain compatible with the Docker runtime (Python 3.13
   in `Dockerfile`), especially for packages like NumPy that have strict Python
   version constraints.
4. If `pip-tools` is not available in the environment, update `requirements.txt`
   manually by pinning versions (preferably using versions already vetted in a
   trusted environment or existing virtual environment).

## Periodic dependency audits
- Run a vulnerability scan at least quarterly (or before releases) using
  `pip-audit`:
  ```bash
  python -m pip install --upgrade pip-audit
  pip-audit -r requirements.txt
  pip-audit --no-deps --disable-pip -r requirements-nodeps.txt
  ```
- Record any remediation notes and follow up by updating `requirements.in` and
  re-pinning `requirements.txt`.
