# Dependency update & audit process

## Files
- `requirements.in`: Source list of top-level dependencies.
- `requirements.txt`: Fully pinned production dependencies.

## Updating dependencies
1. Update `requirements.in` with the desired top-level packages.
2. If `pip-tools` is available, regenerate `requirements.txt` with hashes:
   ```bash
   python -m pip install --upgrade pip-tools
   pip-compile --generate-hashes --output-file requirements.txt requirements.in
   ```
3. If `pip-tools` is not available in the environment, update `requirements.txt`
   manually by pinning versions (preferably using versions already vetted in a
   trusted environment or existing virtual environment).

## Periodic dependency audits
- Run a vulnerability scan at least quarterly (or before releases) using
  `pip-audit`:
  ```bash
  python -m pip install --upgrade pip-audit
  pip-audit -r requirements.txt
  ```
- Record any remediation notes and follow up by updating `requirements.in` and
  re-pinning `requirements.txt`.
