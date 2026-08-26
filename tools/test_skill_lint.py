#!/usr/bin/env python3
"""Acceptance suite for the skill linter.

Run from the repo root:

    python3 tools/test_skill_lint.py

Standard library only. Three groups of tests carry the weight:

1. Seeded-defect fixtures under tools/fixtures/cases. Each fixture directory is
   a miniature repo root holding one planted defect. Every test asserts both
   that the expected code fires and that no other code fires, because a check
   that reports on everything is as useless as one that reports on nothing.
2. False-positive fixtures. These cover the misfires that would get the linter
   switched off, so each one asserts silence.
3. The real repo corpus. This is the definition of done for the whole project.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
CASES = TOOLS / "fixtures" / "cases"
GAPS_FILE = TOOLS / "fixtures" / "known_gaps.json"
ENTRY = TOOLS / "lint_skills.py"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


# --- Recorded corpus state after the conductor, README, and scannable fixes ---
#
# Raw character counts, straight off disk. The linter reports on the prose view,
# where a character sitting inside a code span is masked out, so the linter's
# own numbers can be lower. Both sets are recorded because the spec asks for
# both, and only the derived prose-view numbers are asserted against findings.

EM_DASH_RAW = {
    "improve-codebase-architecture/SKILL.md": 8,
    "improve-codebase-architecture/REFERENCE.md": 3,
}
SEMICOLON_RAW = {
    "improve-codebase-architecture/REFERENCE.md": 1,
    "prose/SKILL.md": 8,
    "recall/SKILL.md": 3,
    "technical-writing/SKILL.md": 1,
    "unslop/SKILL.md": 1,
}

# What the linter itself reports, one finding per prose-view occurrence. Every
# remaining occurrence sits in prose, so raw and prose-view counts agree.
EM_DASH_LINTER = dict(EM_DASH_RAW)
SEMICOLON_LINTER = dict(SEMICOLON_RAW)
EM_DASH_PROSE_VIEW_TOTAL = 11
SEMICOLON_PROSE_VIEW_TOTAL = 14

EM_DASH = "—"
EN_DASH = "–"

# The multi-occurrence fixture that the count-map baseline is tested against.
# Four em dashes and two semicolons in one file, so both keys start above one.
COUNTED_CASE = "baseline_counts"
COUNTED_MD = "counted-skill/SKILL.md"
COUNTED_EM_DASH_LINES = (8, 9, 10, 11)
COUNTED_SEMICOLON_LINES = (13, 14)
EM_DASH_KEY = "SK201\t%s\tem dash, use a period or a comma" % COUNTED_MD
SEMICOLON_KEY = "SK203\t%s\tsemicolon, use a period instead" % COUNTED_MD
NEW_EM_DASH_LINE = "The cleanup runs after %s the archive follows." % EM_DASH
BUG_LINE = "A new line with an em dash %s and a semicolon; plus TODO." % EM_DASH

DEFECT_2_PATH = "improve-codebase-architecture/SKILL.md"
DEFECT_2_NEEDLE = ".william/rfcs/"
DEFECT_4_SKILL = "improve-codebase-architecture"
DEFECT_7_PATH = "recall/SKILL.md"


# --- Module loading -----------------------------------------------------------


def load(name: str):
    """Import a linter module, turning a missing unit into a clear failure."""
    try:
        return importlib.import_module("skill_lint." + name)
    except ImportError as exc:
        raise AssertionError(
            "skill_lint.%s is missing or fails to import: %s" % (name, exc)
        ) from exc


def run_structure(skills, root, check_installed=False):
    structure = load("checks_structure")
    if check_installed:
        return list(structure.run(skills, root, check_installed=True))
    return list(structure.run(skills, root))


def lint_tree(root, check_installed=False):
    """Findings for one tree, matching what the CLI reports."""
    core = load("core")
    prose = load("checks_prose")
    root = Path(root).resolve()
    skills = core.discover_skills(root)
    md_paths = core.repo_markdown(root)
    findings = run_structure(skills, root, check_installed=check_installed)
    findings += list(prose.run(md_paths, root))
    text_by_path = {
        path.resolve().relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in md_paths
    }
    return list(core.apply_suppressions(findings, text_by_path))


def codes_of(findings) -> set:
    return {f.code for f in findings}


def lines_of(findings, code, path=None) -> set:
    return {
        f.line
        for f in findings
        if f.code == code and (path is None or f.path == path)
    }


def cli(*args, cwd=None):
    """Run the linter entry point and return the completed process."""
    if not ENTRY.is_file():
        raise AssertionError("%s is missing, the CLI unit has not landed" % ENTRY)
    return subprocess.run(
        [sys.executable, str(ENTRY), *[str(a) for a in args]],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
    )


def parse_json_output(text: str):
    """Pull the finding list out of JSON-format CLI output."""
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise AssertionError("no JSON list in CLI output: %r" % text[:400])
    return json.loads(text[start : end + 1])


# --- Seeded-defect fixtures ---------------------------------------------------


class SeededDefectTest(unittest.TestCase):
    """One planted defect per fixture, asserted with no collateral findings.

    Line policy. Body-level codes get an exact line assertion. Frontmatter-level
    codes get a small set of acceptable lines, because a parse failure or a
    missing key has no single offending line. Whole-skill codes such as the word
    budget and the routing collision get no line assertion at all.
    """

    def check(self, case, code, lines=None, allowed_lines=None, check_installed=False):
        findings = lint_tree(CASES / case, check_installed=check_installed)
        self.assertEqual(
            codes_of(findings),
            {code},
            "%s: expected only %s, got %s"
            % (case, code, sorted(str(f) for f in findings)),
        )
        got = lines_of(findings, code)
        if lines is not None:
            self.assertEqual(got, set(lines), "%s: wrong lines for %s" % (case, code))
        elif allowed_lines is not None:
            self.assertTrue(
                got <= set(allowed_lines),
                "%s: %s reported lines %s, expected within %s"
                % (case, code, sorted(got), sorted(allowed_lines)),
            )
            self.assertTrue(got, "%s: %s reported no line at all" % (case, code))
        return findings

    def test_clean_skill_is_silent(self):
        findings = lint_tree(CASES / "clean")
        self.assertEqual(findings, [], "clean fixture must produce zero findings")

    def test_sk001_frontmatter_parse_failure(self):
        self.check("sk001", "SK001", allowed_lines={0, 1, 3})

    def test_sk002_name_not_kebab_case(self):
        self.check("sk002", "SK002", allowed_lines={0, 2})

    def test_sk003_name_does_not_match_directory(self):
        self.check("sk003", "SK003", allowed_lines={0, 2})

    def test_sk004_description_missing(self):
        self.check("sk004", "SK004", allowed_lines={0, 1, 2, 3})

    def test_sk005_description_too_short(self):
        self.check("sk005", "SK005", allowed_lines={0, 3})

    def test_sk006_link_to_missing_local_file(self):
        self.check("sk006", "SK006", lines={8})

    def test_sk007_backticked_path_does_not_resolve(self):
        self.check("sk007", "SK007", lines={8})

    def test_sk008_cross_skill_name_without_directory(self):
        # Line 9 names a sibling that does exist and must stay quiet.
        self.check("sk008", "SK008", lines={8})

    def test_sk009_banned_patterns(self):
        # One banned pattern per line: foreign personal path, hardcoded
        # /Users path, TODO, FIXME.
        self.check("sk009", "SK009", lines={8, 9, 10, 11})

    def test_sk101_unknown_frontmatter_key(self):
        self.check("sk101", "SK101", lines={4})

    def test_sk102_body_over_word_budget(self):
        self.check("sk102", "SK102")

    def test_sk103_routing_collision(self):
        self.check("sk103", "SK103")

    def test_sk104_bundled_file_never_referenced(self):
        self.check("sk104", "SK104")

    def test_sk105_disabled_invocation_with_trigger_description(self):
        self.check("sk105", "SK105", allowed_lines={0, 3, 4})

    def test_sk106_skill_not_installed(self):
        self.check("sk106", "SK106", check_installed=True)

    def test_sk106_stays_off_by_default(self):
        findings = lint_tree(CASES / "sk106")
        self.assertEqual(findings, [], "SK106 must not fire without check_installed")

    def test_sk201_em_dash(self):
        self.check("sk201", "SK201", lines={8})

    def test_sk202_en_dash_as_dash(self):
        self.check("sk202", "SK202", lines={8})

    def test_sk203_semicolon(self):
        self.check("sk203", "SK203", lines={8})

    def test_sk204_parenthesised_plural(self):
        self.check("sk204", "SK204", lines={8})

    def test_sk205_slash_construction(self):
        # Line 9 pins digit-bearing tokens like browser/E2E, which the first
        # letters-only pattern missed.
        self.check("sk205", "SK205", lines={8, 9})

    def test_sk206_title_case_heading(self):
        self.check("sk206", "SK206", lines={8})

    def test_sk207_ai_vocabulary(self):
        self.check("sk207", "SK207", lines={8})

    def test_sk208_decorative_emoji(self):
        self.check("sk208", "SK208", lines={8})

    def test_sk209_curly_quote(self):
        self.check("sk209", "SK209", lines={8})

    def test_sk210_filler_phrase(self):
        self.check("sk210", "SK210", lines={8})

    def test_sk211_excessive_hedging(self):
        self.check("sk211", "SK211", lines={8})

    def test_sk212_abstract_metaphor_noun(self):
        self.check("sk212", "SK212", lines={8})

    def test_sk213_fancy_word(self):
        self.check("sk213", "SK213", lines={8})


# --- False-positive guards ----------------------------------------------------


class FalsePositiveTest(unittest.TestCase):
    """Misfires that would get the linter switched off. Each asserts silence."""

    def silent(self, case, code=None):
        findings = lint_tree(CASES / case)
        if code is not None:
            self.assertNotIn(
                code,
                codes_of(findings),
                "%s: %s must not fire here" % (case, code),
            )
        self.assertEqual(
            findings,
            [],
            "%s: expected no findings, got %s"
            % (case, sorted(str(f) for f in findings)),
        )

    def test_bare_script_name_is_not_a_path(self):
        # budget.mjs has no directory part, so it is not path-like.
        self.silent("fp_budget", "SK007")

    def test_skill_name_in_free_prose_is_not_a_reference(self):
        # "compare them in prose" is English, not a pointer at the prose skill.
        self.silent("fp_prose_words", "SK008")

    def test_proper_noun_headings_are_not_title_case(self):
        # Global English, Markdown file, Phase 2.
        self.silent("fp_headings", "SK206")

    def test_duty_pattern_and_date_are_not_slash_constructions(self):
        # 24/7 and 2026/08/26.
        self.silent("fp_slashes", "SK205")

    def test_fenced_and_quoted_text_triggers_nothing(self):
        self.silent("fp_fenced")


# --- Real repo corpus ---------------------------------------------------------


class RepoCorpusTest(unittest.TestCase):
    """The acceptance corpus. These four defects define done for the project."""

    @classmethod
    def setUpClass(cls):
        cls.findings = lint_tree(REPO)

    def prose_view_lines(self, rel_path, needle):
        core = load("core")
        text = (REPO / rel_path).read_text(encoding="utf-8")
        view = core.prose_view(text)
        return {
            idx
            for idx, line in enumerate(view.split("\n"), start=1)
            if needle in line
        }

    def test_raw_character_counts_at_head(self):
        """Guards the corpus itself. A failure here means the repo drifted."""
        for rel, expected in EM_DASH_RAW.items():
            got = (REPO / rel).read_text(encoding="utf-8").count(EM_DASH)
            self.assertEqual(got, expected, "%s em dash count drifted" % rel)
        for rel, expected in SEMICOLON_RAW.items():
            got = (REPO / rel).read_text(encoding="utf-8").count(";")
            self.assertEqual(got, expected, "%s semicolon count drifted" % rel)
        self.assertEqual(sum(EM_DASH_RAW.values()), 11)
        self.assertEqual(sum(SEMICOLON_RAW.values()), 14)

    def test_defect_2_sk009_foreign_personal_path(self):
        path = REPO / DEFECT_2_PATH
        lines = [
            idx
            for idx, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
            if DEFECT_2_NEEDLE in line
        ]
        self.assertEqual(lines, [76], "corpus drifted, .william/rfcs/ moved")
        self.assertEqual(
            lines_of(self.findings, "SK009", DEFECT_2_PATH),
            {76},
            "SK009 must fire on the foreign personal path at line 76",
        )

    def test_defect_7_sk105_recall(self):
        self.assertIn(
            "SK105",
            codes_of([f for f in self.findings if f.path == DEFECT_7_PATH]),
            "SK105 must fire on recall, which disables model invocation while "
            "its description is written as an auto-trigger",
        )
        others = {
            f.path for f in self.findings if f.code == "SK105"
        } - {DEFECT_7_PATH}
        self.assertEqual(others, set(), "SK105 fired outside recall")

    def test_defect_8_em_dashes(self):
        expected_files = set(EM_DASH_RAW)
        got_files = {f.path for f in self.findings if f.code == "SK201"}
        self.assertEqual(got_files, expected_files, "SK201 file set is wrong")
        for rel in sorted(expected_files):
            want_lines = self.prose_view_lines(rel, EM_DASH)
            self.assertEqual(
                lines_of(self.findings, "SK201", rel),
                want_lines,
                "%s: SK201 lines do not match the prose view" % rel,
            )
            count = len([f for f in self.findings if f.code == "SK201" and f.path == rel])
            self.assertEqual(
                count,
                self.prose_view_count(rel, EM_DASH),
                "%s: SK201 count does not match the prose view" % rel,
            )
            self.assertEqual(count, EM_DASH_LINTER[rel], "%s: SK201 count drifted" % rel)
        self.assertEqual(
            len([f for f in self.findings if f.code == "SK201"]),
            EM_DASH_PROSE_VIEW_TOTAL,
        )
        self.assertEqual(self.total_prose_view(EM_DASH, expected_files), EM_DASH_PROSE_VIEW_TOTAL)

    def test_defect_8_semicolons(self):
        expected_files = set(SEMICOLON_RAW)
        got_files = {f.path for f in self.findings if f.code == "SK203"}
        self.assertEqual(got_files, expected_files, "SK203 file set is wrong")
        for rel in sorted(expected_files):
            want_lines = self.prose_view_lines(rel, ";")
            self.assertEqual(
                lines_of(self.findings, "SK203", rel),
                want_lines,
                "%s: SK203 lines do not match the prose view" % rel,
            )
            count = len([f for f in self.findings if f.code == "SK203" and f.path == rel])
            self.assertEqual(
                count,
                self.prose_view_count(rel, ";"),
                "%s: SK203 count does not match the prose view" % rel,
            )
            self.assertEqual(count, SEMICOLON_LINTER[rel], "%s: SK203 count drifted" % rel)
        self.assertEqual(
            len([f for f in self.findings if f.code == "SK203"]),
            SEMICOLON_PROSE_VIEW_TOTAL,
        )
        self.assertEqual(self.total_prose_view(";", expected_files), SEMICOLON_PROSE_VIEW_TOTAL)

    def test_defect_8_touches_every_listed_file(self):
        for rel in sorted(set(EM_DASH_RAW) | set(SEMICOLON_RAW)):
            hits = [f for f in self.findings if f.path == rel and f.code in ("SK201", "SK203")]
            self.assertTrue(hits, "%s: expected at least one em dash or semicolon finding" % rel)

    def test_defect_4_sk106_only_uninstalled_skill(self):
        findings = lint_tree(REPO, check_installed=True)
        flagged = set()
        for finding in findings:
            if finding.code == "SK106":
                flagged.add(finding.path.split("/")[0])
        self.assertEqual(
            flagged,
            {DEFECT_4_SKILL},
            "SK106 must name improve-codebase-architecture and nothing else",
        )

    def test_repo_run_exits_nonzero(self):
        result = cli(REPO)
        self.assertNotEqual(
            result.returncode, 0, "the current repo has real defects and must fail"
        )
        self.assertIn("across", result.stdout, "missing the summary line")

    def prose_view_count(self, rel_path, needle):
        core = load("core")
        view = core.prose_view((REPO / rel_path).read_text(encoding="utf-8"))
        return view.count(needle)

    def total_prose_view(self, needle, rels):
        return sum(self.prose_view_count(rel, needle) for rel in rels)


# --- Zero-match guard ---------------------------------------------------------


class ZeroMatchGuardTest(unittest.TestCase):
    """A suite that can pass against nothing is worse than no suite."""

    def test_empty_directory_reports_sk010(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = cli(tmp)
            self.assertIn("SK010", result.stdout + result.stderr)
            self.assertNotEqual(result.returncode, 0)

    def test_empty_directory_discovers_nothing(self):
        core = load("core")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(core.discover_skills(Path(tmp)), [])


# --- Baseline -----------------------------------------------------------------


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def copy_case(self, case, name):
        dest = self.root / name
        shutil.copytree(CASES / case, dest)
        return dest

    def test_baseline_suppresses_then_catches_new_defect(self):
        tree = self.copy_case("sk201", "tree")
        baseline = self.root / "baseline.json"

        written = cli(tree, "--write-baseline", baseline)
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertTrue(baseline.is_file(), "baseline file was not written")
        data = json.loads(baseline.read_text(encoding="utf-8"))
        self.assertEqual(data.get("version"), 2)
        self.assertTrue(data.get("counts"), "baseline holds no counts")

        clean = cli(tree, "--baseline", baseline)
        self.assertEqual(
            clean.returncode, 0, "a run against its own baseline must exit 0"
        )

        skill_md = tree / "sk201-skill" / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8")
            + "\nThe build ran; the report followed.\n",
            encoding="utf-8",
        )
        after = cli(tree, "--baseline", baseline, "--format", "json")
        self.assertNotEqual(after.returncode, 0, "a new error must fail the run")
        reported = parse_json_output(after.stdout)
        self.assertEqual(
            {row["code"] for row in reported},
            {"SK203"},
            "only the new finding may be reported",
        )

    def test_finding_key_is_line_number_independent(self):
        source = self.copy_case("sk201", "source")
        baseline = self.root / "shift.json"
        written = cli(source, "--write-baseline", baseline)
        self.assertEqual(written.returncode, 0, written.stderr)

        shifted = self.copy_case("sk201", "shifted")
        target = shifted / "sk201-skill" / "SKILL.md"
        lines = target.read_text(encoding="utf-8").split("\n")
        # Push the offending line down without changing its text.
        lines[7:7] = ["", "", "", "", ""]
        target.write_text("\n".join(lines), encoding="utf-8")

        result = cli(shifted, "--baseline", baseline, "--format", "json")
        self.assertEqual(
            result.returncode,
            0,
            "a baselined finding must still match after its line moves",
        )
        self.assertEqual(parse_json_output(result.stdout), [])

    def test_key_excludes_the_line_number(self):
        core = load("core")
        first = core.Finding("SK201", "error", "a/SKILL.md", 8, "em dash in prose")
        second = core.Finding("SK201", "error", "a/SKILL.md", 99, "em dash in prose")
        self.assertEqual(first.key(), second.key())
        self.assertNotIn("8", first.key().split("\t")[0])


# --- Baseline counting --------------------------------------------------------


class BaselineCountTest(unittest.TestCase):
    """The count map, which is what makes the pre-commit gate worth running.

    Finding.key() deliberately carries no line number, so a baselined finding
    survives unrelated edits above it. The cost is that every em dash in one
    file collapses into a single key. A baseline that stores only the set of
    keys therefore swallows an eighth em dash in a file that already had seven,
    which is exactly what a developer produces when editing a file that already
    has findings. Storing a count per key closes that hole while keeping the
    line-shift immunity, so both properties are pinned here.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tree = self.root / "tree"
        shutil.copytree(CASES / COUNTED_CASE, self.tree)
        self.md = self.tree / COUNTED_MD
        self.baseline = self.root / "baseline.json"

        written = cli(self.tree, "--write-baseline", self.baseline)
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertTrue(self.baseline.is_file(), "baseline file was not written")
        settled = cli(self.tree, "--baseline", self.baseline)
        self.assertEqual(
            settled.returncode, 0, "a run against its own baseline must exit 0"
        )

    # --- fixture helpers ---

    def lines(self):
        return self.md.read_text(encoding="utf-8").split("\n")

    def write(self, lines):
        self.md.write_text("\n".join(lines), encoding="utf-8")

    def occurrence_lines(self, needle):
        """1-based file lines currently holding needle."""
        return [
            idx for idx, line in enumerate(self.lines(), start=1) if needle in line
        ]

    def gate(self):
        """Run the gate the way a git hook does and return (process, findings)."""
        result = cli(self.tree, "--baseline", self.baseline, "--format", "json")
        return result, parse_json_output(result.stdout)

    # --- tests ---

    def test_extra_occurrence_of_a_baselined_type_is_caught(self):
        """The regression that shipped. One more of an already-baselined type."""
        lines = self.lines()
        lines[-1:] = [NEW_EM_DASH_LINE, ""]
        self.write(lines)

        present = self.occurrence_lines(EM_DASH)
        self.assertEqual(
            len(present),
            len(COUNTED_EM_DASH_LINES) + 1,
            "fixture edit did not add exactly one em dash",
        )

        result, reported = self.gate()
        self.assertNotEqual(
            result.returncode,
            0,
            "an extra occurrence of a baselined type must fail the gate, "
            "otherwise the baseline hides every repeat offence",
        )
        self.assertEqual(
            len(reported),
            1,
            "only the excess occurrence may be reported, got %s" % reported,
        )
        row = reported[0]
        self.assertEqual(row["code"], "SK201")
        self.assertEqual(row["path"], COUNTED_MD)
        self.assertIn(
            row["line"],
            present,
            "the reported line must name a real em dash, not a placeholder",
        )
        # Pinned rule: sort by line, skip the first baseline_count occurrences.
        self.assertEqual(row["line"], present[-1])

    def test_removing_an_occurrence_still_passes(self):
        lines = self.lines()
        del lines[COUNTED_EM_DASH_LINES[-1] - 1]
        self.write(lines)
        self.assertEqual(
            len(self.occurrence_lines(EM_DASH)), len(COUNTED_EM_DASH_LINES) - 1
        )

        result, reported = self.gate()
        self.assertEqual(
            result.returncode,
            0,
            "a count below the baseline is progress and must exit 0: %s" % result.stdout,
        )
        self.assertEqual(reported, [])

    def test_line_shift_without_a_count_change_still_passes(self):
        """Line-shift immunity is the reason key() omits the line. Guard it."""
        lines = self.lines()
        lines[4:4] = ["", "", "", "", ""]  # just after the closing frontmatter ---
        self.write(lines)

        shifted = self.occurrence_lines(EM_DASH)
        self.assertEqual(
            shifted,
            [line + 5 for line in COUNTED_EM_DASH_LINES],
            "the edit must move every finding, or the test proves nothing",
        )
        self.assertEqual(
            self.occurrence_lines(";"),
            [line + 5 for line in COUNTED_SEMICOLON_LINES],
        )

        result, reported = self.gate()
        self.assertEqual(
            result.returncode,
            0,
            "moving a baselined finding must not fail the gate: %s" % result.stdout,
        )
        self.assertEqual(reported, [])

    def test_one_key_rises_while_another_falls(self):
        lines = self.lines()
        del lines[COUNTED_SEMICOLON_LINES[-1] - 1]
        lines[-1:] = [NEW_EM_DASH_LINE, ""]
        self.write(lines)
        self.assertEqual(len(self.occurrence_lines(EM_DASH)), 5)
        self.assertEqual(len(self.occurrence_lines(";")), 1)

        result, reported = self.gate()
        self.assertNotEqual(result.returncode, 0, "the risen key must fail the gate")
        self.assertEqual(
            [row["code"] for row in reported],
            ["SK201"],
            "only the key whose count rose may be reported, got %s" % reported,
        )
        self.assertEqual(reported[0]["line"], self.occurrence_lines(EM_DASH)[-1])

    def test_version_1_baseline_is_rejected_loudly(self):
        """A stale baseline must stop the run, never be misread as empty."""
        legacy = self.root / "legacy.json"
        legacy.write_text(
            json.dumps({"version": 1, "keys": [EM_DASH_KEY, SEMICOLON_KEY]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        result = cli(self.tree, "--baseline", legacy)
        self.assertEqual(
            result.returncode,
            2,
            "a version 1 baseline is a usage error, not a clean run: %s"
            % (result.stdout + result.stderr),
        )
        self.assertIn(
            "make baseline",
            result.stdout + result.stderr,
            "the message must tell the user how to regenerate the baseline",
        )

    def test_write_baseline_emits_version_2_counts(self):
        raw = self.baseline.read_text(encoding="utf-8")
        self.assertTrue(raw.endswith("\n"), "the baseline file must end with a newline")

        data = json.loads(raw)
        self.assertEqual(data.get("version"), 2)
        self.assertNotIn("keys", data, "the version 1 key list must be gone")

        counts = data.get("counts")
        self.assertIsInstance(counts, dict, "counts must be a key to count object")
        for key, value in counts.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, int)
            self.assertNotIsInstance(value, bool)
            self.assertGreater(value, 0)
        self.assertEqual(
            list(counts), sorted(counts), "counts keys must be written sorted"
        )
        self.assertEqual(counts.get(EM_DASH_KEY), len(COUNTED_EM_DASH_LINES))
        self.assertEqual(counts.get(SEMICOLON_KEY), len(COUNTED_SEMICOLON_LINES))


class RealRepoGateTest(unittest.TestCase):
    """End to end on a copy of the real repo, the scenario that shipped broken.

    README.md already carries seven em dashes and one semicolon at baseline, so
    an eighth em dash used to vanish into the baseline and the gate exited 0.
    """

    def test_new_defects_in_an_already_baselined_file_fail_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(
                REPO, copy, ignore=shutil.ignore_patterns(".git", "node_modules")
            )
            baseline = Path(tmp) / "baseline.json"

            written = cli(copy, "--write-baseline", baseline)
            self.assertEqual(written.returncode, 0, written.stderr)
            settled = cli(copy, "--baseline", baseline)
            self.assertEqual(
                settled.returncode,
                0,
                "an untouched copy must match its own baseline: %s" % settled.stdout,
            )

            # SK009 covers repo markdown no skill owns, the root README included,
            # so the same line fires all three codes in both files.
            for rel in ("README.md", "conductor/SKILL.md"):
                target = copy / rel
                target.write_text(
                    target.read_text(encoding="utf-8") + "\n" + BUG_LINE + "\n",
                    encoding="utf-8",
                )

            result = cli(copy, "--baseline", baseline, "--format", "json")
            self.assertNotEqual(
                result.returncode,
                0,
                "brand new defects in a baselined file must fail the gate",
            )
            reported = parse_json_output(result.stdout)
            self.assertEqual(
                {row["code"] for row in reported},
                {"SK201", "SK203", "SK009"},
                "the gate must name every new code, got %s" % reported,
            )
            by_path = {}
            for row in reported:
                by_path.setdefault(row["path"], set()).add(row["code"])
            self.assertEqual(
                by_path,
                {
                    "README.md": {"SK201", "SK203", "SK009"},
                    "conductor/SKILL.md": {"SK201", "SK203", "SK009"},
                },
                "no file beyond the two edited ones may be reported",
            )
            self.assertEqual(
                len(reported), 6, "one finding per new defect, got %s" % reported
            )


# --- Masking invariants -------------------------------------------------------


class MaskingInvariantTest(unittest.TestCase):
    """Every reported line number rests on these two properties."""

    @classmethod
    def sources(cls):
        core = load("core")
        paths = list(core.repo_markdown(REPO))
        paths += sorted(CASES.rglob("*.md"))
        return paths

    def test_masking_preserves_length_and_line_count(self):
        core = load("core")
        helpers = [
            core.mask_fenced,
            core.mask_inline_code,
            core.mask_blockquotes,
            core.mask_urls,
            core.prose_view,
        ]
        paths = self.sources()
        self.assertTrue(paths, "found no markdown to check")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for helper in helpers:
                out = helper(text)
                self.assertEqual(
                    len(out),
                    len(text),
                    "%s changed length in %s" % (helper.__name__, path),
                )
                self.assertEqual(
                    out.count("\n"),
                    text.count("\n"),
                    "%s changed line count in %s" % (helper.__name__, path),
                )

    def test_masking_replaces_with_spaces_only(self):
        core = load("core")
        text = (REPO / "README.md").read_text(encoding="utf-8")
        view = core.prose_view(text)
        for original, masked in zip(text, view):
            self.assertTrue(
                masked == original or masked == " ",
                "masking must only blank characters out",
            )


# --- Discovery skips the linter's own tree ------------------------------------


class DiscoveryTest(unittest.TestCase):
    def test_discovery_skips_tools(self):
        core = load("core")
        names = {skill.name for skill in core.discover_skills(REPO)}
        self.assertNotIn("tools", names)
        self.assertIn("conductor", names)

    def test_repo_markdown_skips_tools(self):
        core = load("core")
        paths = core.repo_markdown(REPO)
        offenders = [p for p in paths if "tools" in p.resolve().parts]
        self.assertEqual(offenders, [], "fixtures must stay out of the repo run")
        self.assertIn(REPO / "README.md", [p.resolve() for p in paths])


# --- Documented gaps ----------------------------------------------------------


class KnownGapsTest(unittest.TestCase):
    """Corpus defects 1, 3, 5, and 6 are not statically checkable here.

    Faking a test for them would be worse than admitting the gap. The manifest
    records each one, and this test keeps its locations honest so the gaps stay
    visible instead of rotting away.
    """

    def test_manifest_parses_and_locations_still_exist(self):
        self.assertTrue(GAPS_FILE.is_file(), "%s is missing" % GAPS_FILE)
        data = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
        gaps = data["gaps"]
        self.assertEqual(
            {gap["id"] for gap in gaps},
            {
                "defect-3-half-finished-rfc-conversion",
                "defect-5-routing-bypass",
                "defect-6-cross-skill-self-modification",
            },
        )
        for gap in gaps:
            for field in ("defect", "why_not_checkable", "what_would_catch_it"):
                self.assertTrue(gap.get(field), "%s: %s is empty" % (gap["id"], field))
            for location in [gap] + list(gap.get("related", [])):
                self.check_location(gap["id"], location)

    def check_location(self, gap_id, location):
        path = REPO / location["path"]
        self.assertTrue(path.is_file(), "%s: %s is gone" % (gap_id, location["path"]))
        lines = path.read_text(encoding="utf-8").split("\n")
        self.assertGreaterEqual(
            len(lines),
            location["line"],
            "%s: %s is now shorter than line %s"
            % (gap_id, location["path"], location["line"]),
        )
        anchor = location["anchor"]
        found = [i + 1 for i, line in enumerate(lines) if anchor in line]
        self.assertTrue(
            found,
            "%s: anchor text has vanished from %s"
            % (gap_id, location["path"]),
        )
        # Anchor must sit at the recorded line. Whole-file matching lets the
        # recorded line rot silently, which is the drift this manifest exists to stop.
        self.assertIn(
            location["line"],
            found,
            "%s: %s line %s no longer holds the anchor, it moved to %s"
            % (gap_id, location["path"], location["line"], found),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
