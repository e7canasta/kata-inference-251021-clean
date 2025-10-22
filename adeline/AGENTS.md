# Repository Guidelines

## Project Structure & Module Organization
The package root exposes `adeline` with entrypoint `__main__.py` for `python -m adeline`. Runtime controllers live in `app/`, MQTT control-plane logic in `control/`, and inference models plus ROI/stabilization handlers in `inference/`. Configuration schemas sit in `config/`, reusable datasets and fixtures in `data/`, visualization helpers in `visualization/`, and automated checks in `scripts/`. Tests are collected under `tests/` and mirror feature folders for quick discovery.

## Build, Test & Development Commands
Use `python -m adeline` to launch the default pipeline against the configured MQTT endpoints. Run `./scripts/validate.sh` for the full pre-flight (mypy, all pytest suites, config validation); append `--fast` to skip slow markers. During tight loops, prefer `pytest -m unit` for focused checks and `mypy . --config-file mypy.ini` to track typing drift.

## Coding Style & Naming Conventions
Target Python 3.10 with 4-space indentation and standard library typing. Keep public APIs centralized in `__init__.py` exports and document new modules with module docstrings. Align with existing naming—controller classes in `PascalCase`, helper functions in `snake_case`, constants in `UPPER_SNAKE`, and MQTT topics grouped under descriptive enums or dataclasses. Run formatters or linters locally if introduced, and never commit ANSI-colored logs or notebook checkpoints.

## Testing Guidelines
Pytest auto-discovers files named `test_*.py`, classes starting `Test`, and functions `test_*`; match those patterns for new cases. Reuse markers defined in `pytest.ini` (`unit`, `integration`, `slow`, `roi`, `mqtt`, `stabilization`) so CI selectors stay reliable. Favour fixture reuse over ad-hoc setup, and add regression tests beside the module they exercise. When touching config parsing, include a YAML round-trip test invoking `AdelineConfig.from_yaml`.

## Commit & Pull Request Guidelines
Follow the lightweight conventional-commit style visible in history: lowercase type prefixes (`feat`, `docs`, `fix`, `refactor`, `test`) followed by an imperative summary under ~72 characters. Group related changes per commit and include follow-up context in the body when behaviour shifts. Pull requests should link issues or test cases, outline validation steps run (`./scripts/validate.sh --fast`, targeted pytest markers, manual MQTT checks), and attach screenshots or logs for UI/visualization tweaks. Flag breaking changes or new external dependencies explicitly in the description.

## Configuration & Runtime Notes
Default settings live in `config/adeline/`; keep overrides in environment-specific files that extend the schema. Validate any new YAML with `python -m config.schemas` or via the validation script before pushing. Store credentials outside the repo and use `.env` files ignored by git for local secrets.
