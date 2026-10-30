# specklewidgets is a Python package with a JS widget inside, so it has two toolchains: npm
# for js/ and uv for the Python. `just` lists the recipes; CI runs the same ones.
#
# Recipes run in sh (Git Bash on Windows). The package.json scripts they call stay single
# commands, because npm runs those in cmd.exe on Windows.

# List the recipes
default:
    @just --list --unsorted

# Install the locked JS and Python dependencies
setup: setup-js setup-py

# npm ci: the JS dependencies of package-lock.json
setup-js:
    npm ci

# uv sync: the Python dependencies of uv.lock
setup-py:
    uv sync --locked

# Type-check js/ and bundle it into src/specklewidgets/static/ (committed)
build:
    npm run build

# Rebuild on change; ANYWIDGET_HMR=1 hot-reloads the notebook
dev:
    npm run dev

# Every check except the e2e
check: check-js check-py

# Types, lint, format and unit tests of js/
check-js:
    npm run typecheck
    npm run lint
    npm run fmt:check
    npm run test

# Lint, format, types and tests of the Python package
check-py:
    uv run ruff check
    uv run ruff format --check
    uv run mypy src
    uv run pytest

# Fail when the committed bundle is not the build of the committed js/
check-bundle: build
    git diff --exit-code src/specklewidgets/static

# Format js/ and the Python
fmt:
    npm run fmt
    uv run ruff format

# The example notebook in headless Chromium (needs `npx playwright install chromium` once)
e2e:
    npm run e2e
