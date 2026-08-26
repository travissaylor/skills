.PHONY: check lint lint-ci test baseline install-hooks

.DEFAULT_GOAL := check

# Full findings, no baseline, use to see the real backlog.
lint:
	python3 tools/lint_skills.py

# Baseline-filtered findings, use in commit and CI gates.
lint-ci:
	python3 tools/lint_skills.py --baseline tools/lint_baseline.json

# Runs the linter test suite.
test:
	python3 tools/test_skill_lint.py

# Regenerates the baseline from current findings, run after a deliberate fix.
baseline:
	python3 tools/lint_skills.py --write-baseline tools/lint_baseline.json

# Points git at the version-controlled hooks dir and makes the hook runnable.
install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit

# Compile check, then test, then the baseline-filtered lint. Run before pushing.
check:
	python3 -m compileall -q tools/
	$(MAKE) test
	$(MAKE) lint-ci
