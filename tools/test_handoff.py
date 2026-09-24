#!/usr/bin/env python3
"""Exercise handoff helper output and argument validation in isolated stores.

Run from the repo root: python3 tools/test_handoff.py
Set HANDOFF_TEST_BASH to test a specific Bash executable.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "handoff/scripts/handoff.sh"
TEST_BASH = os.environ.get("HANDOFF_TEST_BASH", "bash")


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.store = self.work / "store with spaces"
        self.project = self.store / "example"
        self.env = os.environ.copy()
        self.env.update(
            HANDOFF_ROOT=str(self.store), HANDOFF_PROJECT="example", HANDOFF_PEERS=""
        )
        # Accidental peer calls fail locally and are visible to the test.
        self.calls = self.work / "peer-calls"
        bin_dir = self.work / "bin"
        bin_dir.mkdir()
        for command in ("ssh", "rsync"):
            stub = bin_dir / command
            stub.write_text('#!/bin/sh\necho called >> "$PEER_CALLS"\nexit 1\n')
            stub.chmod(0o755)
        self.env["PEER_CALLS"] = str(self.calls)
        self.env["PATH"] = str(bin_dir) + os.pathsep + self.env["PATH"]

    def cli(self, *args):
        return subprocess.run(
            [TEST_BASH, str(ENTRY), *map(str, args)],
            cwd=self.work,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def document(self, name, *, branch="main", status="open", mtime=100, text=None):
        self.project.mkdir(parents=True, exist_ok=True)
        path = self.project / name
        path.write_text(
            text if text is not None else
            f"---\nproject: example\nbranch: {branch}\nstatus: {status}\n---\n\n# Goal\nResume work.\n"
        )
        os.utime(path, (mtime, mtime))
        return path

    def paths(self, result):
        return [line.removeprefix("path: ") for line in result.stdout.splitlines()
                if line.startswith("path: ")]

    def test_empty_is_success_with_explicit_status(self):
        result = self.cli("latest")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: empty\n", result.stdout)
        self.assertIn("project: example\n", result.stdout)
        self.assertIn("0 open handoffs", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_latest_selects_newest_open_document(self):
        self.document("older.md", mtime=100)
        newest = self.document("newer file.md", mtime=200)
        self.document("resumed.md", status="resumed", mtime=300)
        result = self.cli("latest")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: found\nproject: example\n", result.stdout)
        self.assertEqual(self.paths(result), [str(newest)])

    def test_branch_all_and_path_combine(self):
        older = self.document("older.md", branch="feature/work", mtime=100)
        newer = self.document("newer.md", branch="feature/work", mtime=200)
        other = self.document("other.md", branch="main", mtime=300)
        self.assertEqual(self.paths(self.cli("latest", "--all")),
                         [str(other), str(newer), str(older)])
        result = self.cli("latest", "--all", "--branch", "feature/work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.paths(result), [str(newer), str(older)])
        result = self.cli("latest", "--path", "--branch", "feature/work", "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(newer), str(older)])
        self.assertEqual(self.paths(self.cli("latest", "--branch", "feature/work")),
                         [str(newer)])

    def test_path_mode_preserves_single_path_and_empty_exit(self):
        for args in (("--path",), ("--all", "--path", "--branch", "absent")):
            with self.subTest(args=args):
                result = self.cli("latest", *args)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
        path = self.document("open.md")
        result = self.cli("latest", "--path")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(path) + "\n")

    def test_branch_without_matches_is_explicit_empty(self):
        self.document("open.md")
        result = self.cli("latest", "--branch", "missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: empty", result.stdout)
        self.assertIn("branch: missing\n", result.stdout)
        self.assertEqual(self.paths(result), [])

    def test_only_complete_frontmatter_supplies_status(self):
        cases = (
            "# Document\nstatus: open\n---\n",
            "---\nbranch: main\n---\nstatus: open\n",
            "---\nstatus: open\nbranch: main\n",
            "---\nstatus: resumed\n---\nstatus: open\n",
        )
        for i, text in enumerate(cases):
            self.document(f"invalid-{i}.md", text=text)
        result = self.cli("latest", "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: empty", result.stdout)

    def test_scalar_quotes_whitespace_and_crlf(self):
        path = self.document("quoted.md", text=(
            '---\r\nstatus: "open"  \r\nbranch: \'feature/work\'\r\n---\r\n'
        ))
        result = self.cli("latest", "--branch", "feature/work", "--path")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(path) + "\n")

    def test_mark_resumed_handles_recognized_crlf_document(self):
        path = self.document("crlf.md", text=(
            '---\r\nstatus: "open"\r\nbranch: main\r\n---\r\nBody\r\n'
        ))
        self.assertEqual(self.cli("latest", "--path").stdout, str(path) + "\n")
        result = self.cli("mark-resumed", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: resumed\n", path.read_text())
        self.assertIn("resumed_on:", path.read_text())
        self.assertIn("status: empty", self.cli("latest").stdout)
        self.assertFalse(self.calls.exists())

    def test_help_is_success_and_has_no_side_effects(self):
        invocations = [(), ("--help",), ("-h",)]
        invocations.extend((command, "--help") for command in
                           ("dir", "new", "latest", "mark-resumed", "sync", "peers"))
        for args in invocations:
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Usage:", result.stdout)
                self.assertEqual(result.stderr, "")
                self.assertFalse(self.store.exists())
                self.assertFalse(self.calls.exists())

    def test_invalid_arguments_fail_before_side_effects(self):
        invocations = (
            ("unknown",), ("--help", "extra"), ("dir", "extra"),
            ("sync", "--unknown"), ("peers", "extra"), ("new",),
            ("new", ""), ("new", "!!!"), ("new", "slug", "extra"),
            ("new", "--unknown"), ("mark-resumed",),
            ("mark-resumed", "file", "extra"), ("mark-resumed", "--unknown"),
            ("latest", "extra"), ("latest", "--unknown"),
            ("latest", "--branch"), ("latest", "--branch", ""),
            ("latest", "--branch", "--all"), ("latest", "--help", "extra"),
        )
        for args in invocations:
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("--help", result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertFalse(self.store.exists())
                self.assertFalse(self.calls.exists())

    def test_invalid_mark_does_not_change_existing_file(self):
        path = self.document("open.md")
        before = path.read_bytes()
        result = self.cli("mark-resumed", path, "extra")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.calls.exists())

    def test_runtime_failure_is_not_empty_success(self):
        self.store.write_text("not a directory")
        result = self.cli("latest")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("status: empty", result.stdout)
        self.assertIn("cannot create store", result.stderr)
        result = self.cli("mark-resumed", "missing.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("existing file", result.stderr)

    def test_new_dir_and_mark_resumed_work_locally(self):
        result = self.cli("new", "My next task")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = Path(result.stdout.strip())
        self.assertEqual(path.parent, self.project)
        self.assertTrue(path.name.endswith("-my-next-task.md"))
        self.assertFalse(path.exists())
        self.assertEqual(self.cli("dir").stdout, str(self.project) + "\n")
        document = self.document(path.name)
        result = self.cli("mark-resumed", document)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: resumed", document.read_text())
        self.assertIn("resumed_on:", document.read_text())
        self.assertIn("local only", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertIn("status: empty", self.cli("latest").stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
