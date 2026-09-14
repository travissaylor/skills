.PHONY: check lint lint-ci test baseline install-hooks install

.DEFAULT_GOAL := check

# Full findings, no baseline, use to see the real backlog.
lint:
	python3 tools/lint_skills.py

# Baseline-filtered findings, use in commit and CI gates.
lint-ci:
	python3 tools/lint_skills.py --baseline tools/lint_baseline.json

# Runs the linter and helper script test suites.
test:
	python3 -m unittest discover -s tools -p 'test_*.py'

# Regenerates the baseline from current findings, run after a deliberate fix.
baseline:
	python3 tools/lint_skills.py --write-baseline tools/lint_baseline.json

# Points git at the version-controlled hooks dir and makes the hook runnable.
install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit

# Symlinks every skill into the Claude, Codex, agents, and Gemini skill directories.
install:
	tools/install_skills.sh

# Compile check, then test, then the baseline-filtered lint. Run before pushing.
check:
	python3 -m compileall -q tools/
	$(MAKE) test
	$(MAKE) lint-ci
