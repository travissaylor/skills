#!/usr/bin/env python3
"""Check executor helper contracts with local fake CLIs, without agent calls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "conductor-multi/scripts/run-unit.sh"
REPORT = {
    "status": "done",
    "files_changed": [],
    "acceptance": [],
    "checks": [],
    "blockers": "",
    "notes": "",
}

FAKE_BACKEND = r'''
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
Path(os.environ["FAKE_CALL"]).write_text(json.dumps(args))
mode = os.environ.get("FAKE_MODE", "success")
report = json.loads(os.environ["FAKE_REPORT"])
print("backend diagnostics", file=sys.stderr)
if Path(sys.argv[0]).name == "codex":
    output = Path(args[args.index("-o") + 1])
    print(json.dumps({"type": "thread.started", "thread_id": "thread-123"}))
    if mode == "failed":
        print(json.dumps({"type": "turn.failed", "error": {"message": "authentication failed\n" + "detail " * 100}}))
    if mode not in ("missing", "failed"):
        output.write_text({
            "malformed": "{invalid",
            "empty": "",
            "array": "[]",
            "multiple": "{}\n{}",
        }.get(mode, json.dumps(report)))
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}))
else:
    if mode == "malformed":
        print('{"status":"SUCCESS","structured_output":{}} trailing')
    elif mode != "empty":
        payload = {"status": "SUCCESS", "conversation_id": "thread-123", "usage": {"input_tokens": 10}}
        if mode == "failed":
            payload.update(status="FAILED", error={"message": "authentication failed\n" + "detail " * 100})
        elif mode == "quoted-status":
            payload["status"] = 'bad "status"'
        elif mode != "missing":
            payload["structured_output"] = [] if mode == "array" else report
        print(json.dumps(payload))
sys.exit(7 if mode == "nonzero" else 0)
'''


@unittest.skipUnless(shutil.which("jq"), "run-unit.sh requires jq")
class RunUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-unit-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.run_dir = self.root / "reports with spaces"
        self.run_dir.mkdir()
        (self.run_dir / "test-unit.brief.md").write_text("Perform the isolated test task.")
        self.call = self.root / "called.json"
        for backend in ("codex", "agy"):
            self.executable(backend, FAKE_BACKEND)
        # Shorten only the helper's polling interval. Production sleeps stay unchanged.
        self.executable("sleep", "import time\ntime.sleep(0.01)\n")
        self.env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_CALL": str(self.call),
            "FAKE_REPORT": json.dumps(REPORT),
            "FAKE_MODE": "success",
        }

    def executable(self, name, body):
        path = self.bin / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)

    def invoke(self, args, mode="success"):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *args],
            cwd=self.root,
            env={**self.env, "FAKE_MODE": mode},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def args(self, backend="codex"):
        return [
            "--backend", backend, "--unit", "test-unit",
            "--run-dir", str(self.run_dir), "--repo", str(self.repo),
        ]

    def metadata(self):
        return json.loads((self.run_dir / "test-unit.meta.json").read_text())

    def test_help_needs_no_executor_or_files(self):
        self.env["PATH"] = "/usr/bin:/bin"
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                result = self.invoke([flag])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Usage:", result.stdout)
                self.assertIn("--stall", result.stdout)
                self.assertFalse(result.stderr)
                self.assertFalse(self.call.exists())
                self.assertEqual(len(list(self.run_dir.iterdir())), 1)

    def test_usage_errors_preserve_existing_artifacts(self):
        artifact = self.run_dir / "test-unit.result.json"
        artifact.write_text("previous report")
        cases = [
            ([], "missing --backend"),
            (["--unknown"], "unknown argument"),
            (["--backend"], "requires a value"),
            (["--backend", "--unit", "x"], "requires a value"),
            (self.args() + ["--model", ""], "requires a value"),
            (self.args() + ["--backend", "other"], "--backend"),
            (self.args() + ["--repo", str(self.root / "absent")], "--repo"),
            (self.args() + ["--run-dir", str(self.root / "absent")], "brief"),
        ]
        for flag in ("--stall", "--max"):
            for value in ("0", "-1", "1.5", "abc", "999999999999999999999999"):
                cases.append((self.args() + [flag, value], flag))
        for args, message in cases:
            with self.subTest(args=args):
                result = self.invoke(args)
                self.assertEqual(result.returncode, 2, result)
                self.assertIn(message, result.stderr)
                self.assertIn("--help", result.stderr)
                self.assertFalse(result.stdout)
                self.assertFalse(self.call.exists())
                self.assertEqual(artifact.read_text(), "previous report")
                self.assertFalse((self.root / "absent").exists())

    def test_success_names_artifacts_and_preserves_metadata(self):
        for backend in ("codex", "agy"):
            with self.subTest(backend=backend):
                result = self.invoke(self.args(backend))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stdout, rf"test-unit \[{backend}\] completed in \d+s")
                for label, suffix in (("report", "result.json"), ("meta", "meta.json"), ("stderr", "stderr")):
                    path = self.run_dir / ("test-unit." + suffix)
                    self.assertIn(f"{label}: {path}", result.stdout)
                    self.assertTrue(path.exists())
                self.assertNotIn("reason:", result.stdout)
                self.assertEqual(json.loads((self.run_dir / "test-unit.result.json").read_text()), REPORT)
                meta = self.metadata()
                self.assertEqual(set(meta), {"backend", "unit", "outcome", "exit_code", "model", "thread_id", "seconds", "usage", "error"})
                self.assertEqual(meta["outcome"], "completed")
                self.assertEqual(meta["thread_id"], "thread-123")
                self.assertEqual(meta["usage"], {"input_tokens": 10})
                self.assertIsNone(meta["error"])

    def test_failures_explain_next_inspection(self):
        for backend in ("codex", "agy"):
            modes = ("missing", "empty", "malformed", "array", "nonzero", "failed")
            if backend == "codex":
                modes += ("multiple",)
            else:
                modes += ("quoted-status",)
            for mode in modes:
                with self.subTest(backend=backend, mode=mode):
                    # A previous run's valid result must never turn this failure into success.
                    (self.run_dir / "test-unit.result.json").write_text(json.dumps(REPORT))
                    result = self.invoke(self.args(backend), mode)
                    self.assertEqual(result.returncode, 1, result)
                    self.assertIn(f"[{backend}] failed", result.stdout)
                    self.assertIn(f"stderr: {self.run_dir}/test-unit.stderr", result.stdout)
                    reasons = [line for line in result.stdout.splitlines() if line.startswith("reason: ")]
                    self.assertEqual(len(reasons), 1, result.stdout)
                    self.assertLessEqual(len(json.loads(reasons[0][8:])), 240)
                    meta = self.metadata()
                    self.assertEqual(meta["outcome"], "failed")
                    self.assertIsNotNone(meta["error"])
                    if mode == "nonzero":
                        self.assertEqual(meta["exit_code"], 7)
                        self.assertIn("code 7", result.stdout)
                    elif mode == "failed":
                        self.assertIn("authentication failed", result.stdout)
                        self.assertGreater(len(meta["error"]["message"]), 240)

    def test_resume_and_model_flags_reach_each_backend(self):
        for backend in ("codex", "agy"):
            with self.subTest(backend=backend):
                result = self.invoke(self.args(backend) + ["--resume", "prior-thread", "--model", "chosen-model", "--max", "120", "--stall", "30"])
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads(self.call.read_text())
                self.assertIn("chosen-model", args)
                self.assertIn("prior-thread", args)
                if backend == "codex":
                    self.assertEqual(args[:3], ["exec", "resume", "prior-thread"])
                    self.assertIn('sandbox_mode="workspace-write"', args)
                    self.assertIn("--output-schema", args)
                else:
                    self.assertIn("--conversation", args)
                    self.assertIn("--json-schema", args)
                    self.assertEqual(args[args.index("--print-timeout") + 1], "120s")


if __name__ == "__main__":
    unittest.main()
