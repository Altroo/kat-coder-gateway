"""Run the real deployment hook with temporary Git history and fake services.

No sudo, network, systemd, model, or compiler is used. GNU-only filesystem
commands are modeled so the same rollback contract runs on macOS and Linux.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "deploy" / "post-receive.sh"

FAKE_COMMAND = r'''
import fcntl
import json
import os
import pathlib
import sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["DEPLOY_TEST_LOG"], "a") as log:
    log.write(json.dumps([name, args]) + "\n")
if name == "sudo":
    os.execvp(args[0], args)
elif name == "flock":
    if os.environ.get("DEPLOY_TEST_BUSY"):
        sys.exit(1)
    fcntl.flock(int(args[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)
elif name == "readlink":
    target = args[-1]
    print(str(pathlib.Path(target).resolve()) if "-f" in args else os.readlink(target))
elif name == "ln":
    os.symlink(args[-2], args[-1])
elif name == "mv":
    os.replace(args[-2], args[-1])
elif name == "make":
    # Compiling must still leave the live code on the old release.
    link = pathlib.Path(os.environ["DEPLOY_TEST_ACTIVE"])
    expected = os.environ.get("DEPLOY_TEST_OLD")
    if expected:
        assert os.readlink(link) == expected
    else:
        assert not link.is_symlink()
    sys.exit(1 if os.environ.get("DEPLOY_TEST_BUILD_FAIL") else 0)
elif name == "systemctl":
    if args[0] == "restart" and os.environ.get("DEPLOY_TEST_RESTART_FAIL"):
        sys.exit(1)
elif name == "curl":
    assert "--connect-timeout" in args and "--max-time" in args
    sys.exit(1 if os.environ.get("DEPLOY_TEST_HEALTH_FAIL") else 0)
elif name == "sleep":
    pass
else:
    raise AssertionError(name)
'''


@unittest.skipIf(os.name == "nt" or not shutil.which("git"), "POSIX hook and Git required")
class GatewayDeploymentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gateway-deploy-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Deployment Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "c").mkdir()
        (self.repo / "c" / "version").write_text("first")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "first")
        self.first = self.git("rev-parse", "HEAD")
        (self.repo / "c" / "version").write_text("second")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "second")
        self.second = self.git("rev-parse", "HEAD")
        self.legacy = self.root / "legacy"
        self.legacy.mkdir()
        (self.legacy / "version").write_text("untouched")
        self.private_env = self.legacy / ".env.production"
        self.private_env.write_text("KAT_TEST_PRIVATE=fixture\n")
        self.private_env.chmod(0o600)
        self.active = self.root / "active"
        self.active.symlink_to(self.legacy)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for command in ("sudo", "flock", "readlink", "ln", "mv", "make", "systemctl", "curl", "sleep"):
            target = self.bin / command
            target.write_text(f"#!{sys.executable}\n" + FAKE_COMMAND)
            target.chmod(0o755)
        self.log = self.root / "commands.jsonl"
        self.config = self.root / "deploy.env"
        config = {"KAT_DEPLOY_GIT_DIR": self.repo / ".git", "KAT_DEPLOY_TARGET": self.legacy,
                  "KAT_DEPLOY_ACTIVE_LINK": self.active, "KAT_DEPLOY_SERVICE": "fixture.service",
                  "KAT_DEPLOY_HEALTH_URL": "http://127.0.0.1:1/health"}
        self.config.write_text("".join(f"{key}={shlex.quote(str(value))}\n" for key, value in config.items()))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, text=True,
                                       stderr=subprocess.STDOUT).strip()

    def run_hook(self, revision=None, ref="refs/heads/main", **changes):
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                   KAT_GATEWAY_DEPLOY_ENV=str(self.config), DEPLOY_TEST_LOG=str(self.log),
                   DEPLOY_TEST_ACTIVE=str(self.active),
                   DEPLOY_TEST_OLD=os.readlink(self.active) if self.active.is_symlink() else "")
        env.update(changes)
        return subprocess.run(["sh", str(HOOK)], input=f"{'0' * 40} {revision or self.first} {ref}\n",
                              text=True, capture_output=True, env=env, timeout=20)

    def commands(self, command):
        rows = self.log.read_text().splitlines() if self.log.exists() else []
        return [args for name, args in map(json.loads, rows) if name == command]

    def test_exact_pushed_revision_and_repeat_release_are_isolated(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        first_release = self.active.resolve()
        self.assertEqual((first_release / "c" / "version").read_text(), "first")
        self.assertEqual((self.legacy / "version").read_text(), "untouched")
        self.assertEqual((first_release / ".env.production").resolve(), self.private_env)
        self.assertEqual(first_release.stat().st_mode & 0o777, 0o755)
        result = self.run_hook(self.second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.active.resolve(), first_release)
        self.assertEqual((first_release / "c" / "version").read_text(), "first")
        self.assertEqual((self.active / "c" / "version").read_text(), "second")

    def test_failed_build_does_not_switch_or_restart(self):
        result = self.run_hook(DEPLOY_TEST_BUILD_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.active.resolve(), self.legacy)
        self.assertEqual(self.commands("systemctl"), [])

    def test_private_config_need_not_be_readable_by_deploy_account(self):
        self.private_env.chmod(0)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.active / ".env.production").resolve(), self.private_env)
        self.assertEqual(self.private_env.stat().st_mode & 0o777, 0)

    def test_failed_health_restores_original_release(self):
        result = self.run_hook(DEPLOY_TEST_HEALTH_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.active.resolve(), self.legacy)
        self.assertEqual((self.legacy / "version").read_text(), "untouched")
        self.assertEqual(len(self.commands("curl")), 30)
        self.assertEqual(len(self.commands("systemctl")), 2)

    def test_failed_restart_restores_original_link(self):
        result = self.run_hook(DEPLOY_TEST_RESTART_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.active.resolve(), self.legacy)

    def test_first_release_failure_removes_only_new_link(self):
        self.active.unlink()
        result = self.run_hook(DEPLOY_TEST_HEALTH_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.active.is_symlink())
        self.assertIn(["stop", "fixture.service"], self.commands("systemctl"))
        self.assertTrue(self.private_env.exists())

    def test_busy_deployment_does_not_build_or_switch(self):
        result = self.run_hook(DEPLOY_TEST_BUSY="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.commands("make"), [])
        self.assertEqual(self.active.resolve(), self.legacy)

    def test_other_branches_and_deletions_do_not_deploy(self):
        for revision, ref in ((self.first, "refs/heads/feature"), ("0" * 40, "refs/heads/main")):
            with self.subTest(ref=ref, revision=revision):
                self.assertEqual(self.run_hook(revision, ref).returncode, 0)
        self.assertEqual(self.commands("make"), [])

    def test_non_symlink_active_directory_is_refused(self):
        self.active.unlink()
        self.active.mkdir()
        result = self.run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.active.is_dir())
        self.assertEqual(self.commands("make"), [])


if __name__ == "__main__":
    unittest.main()
