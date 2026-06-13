# Dustman

Python/PyQt Windows cleaner utility.

Dustman is a local desktop cleaner experiment: a small Windows utility UI for previewing and running cleanup workflows without turning the project into a giant system optimizer.

## Current Scope

- Python desktop app.
- UI stack: PyQt / PyQt-Fluent style dependencies from `requirements.txt`.
- Main entry: `main.py`.
- Target platform: Windows.

## What It Does

- Provides a desktop UI for local cleanup workflows.
- Keeps cleanup behavior in the local app instead of a remote service.
- Serves as a place to test safer Windows cleaner interactions: clear prompts, readable status, and review-before-action behavior.

## Safety Notes

Cleaner tools can damage useful files if the target list is wrong.

- Review cleanup targets before confirming deletion or modification.
- Test in a disposable folder or VM before using on important data.
- Keep machine-specific paths and local config out of commits.
- If `config.json` is used locally, check it before pushing and avoid personal paths or secrets.

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Project Status

Experimental Windows utility. Good enough to keep, but it should grow with preview, confirmation, and rollback-first thinking.

## License

MIT.
