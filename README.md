# ai-hub-demo

A small URL shortener. It is the demo app for [ai-hub](https://github.com/cekinmezyucel/ai-hub):
the agent builds its features from PRD Issues, one step at a time.

Today it only has `GET /health`. Features come through PRDs.

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint
.venv/bin/pytest                                            # test
.venv/bin/uvicorn app.main:app --reload                     # run on :8000
```

CI (`.github/workflows/ci.yml`) runs lint, tests and a Docker build on every PR.
