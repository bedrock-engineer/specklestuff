# specklewidgets is a Python package with a JS widget inside, so it has two toolchains: pnpm
# for the npm package in packages/geospeckle-viewer and the demo page in site/, and uv for the
# Python. `just` lists the recipes; CI runs the same ones.
#
# Recipes run in sh (Git Bash on Windows). The package.json scripts they call stay single
# commands, because pnpm runs those in cmd.exe on Windows.

# List the recipes
default:
    @just --list --unsorted

# Install the locked JS and Python dependencies
setup: setup-js setup-py

# pnpm install: the JS dependencies of pnpm-lock.yaml
setup-js:
    pnpm install --frozen-lockfile

# uv sync: the Python dependencies of uv.lock
setup-py:
    uv sync --locked

# Type-check and bundle the widgets into src/specklewidgets/static/ (committed)
build:
    pnpm run build

# Build the npm package into packages/geospeckle-viewer/dist (not committed)
build-npm:
    pnpm --filter @bedrock-engineer/geospeckle-viewer run build

# Rebuild on change; ANYWIDGET_HMR=1 hot-reloads the notebook
dev:
    pnpm run dev

# Every check except the e2e
check: check-js check-py

# Types, lint, format and unit tests of packages/ and site/
check-js:
    pnpm run typecheck
    pnpm run lint
    pnpm run fmt:check
    pnpm run test

# Lint, format, types and tests of the Python package
check-py:
    uv run ruff check
    uv run ruff format --check
    uv run mypy src
    uv run pytest

# Fail when the committed bundle is not the build of the committed packages/geospeckle-viewer
check-bundle: build
    git diff --exit-code src/specklewidgets/static

# Format the JS and the Python
fmt:
    pnpm run fmt
    uv run ruff format

# The example notebooks and the demo page in headless Chromium (`pnpm exec playwright install chromium` once)
e2e:
    pnpm run e2e

# The demo page's data: Sixty5 from the bimpolars bucket, the OSM map and PDOK's 3D BAG
site-data:
    uv run python site/sixty5.py site/public/data

# The demo page for GitHub Pages, into site/dist (`SITE=bimpolars just site` for bimpolars')
site: site-data
    pnpm run site

# Serve the demo page with hot reload (after `just site-data`)
site-dev:
    pnpm run site:dev

# Receive and send on a real Speckle server with this machine's Speckle account (skips without one)
live:
    uv run pytest -m live
