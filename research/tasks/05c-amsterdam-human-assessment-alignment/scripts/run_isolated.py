#!/usr/bin/env python3
"""Run one historical-checklist assessment in a one-EIP bubblewrap capsule."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml

from common import (
    AUTOMATED_ROOT,
    CONTRACT_PATH,
    PACKAGE_ROOT,
    REPO_ROOT,
    TASK_ROOT,
    StudyError,
    load_yaml,
    now,
    sha256_file,
)
from validate_outputs import ISOLATION_METHOD, validate_automated


CAPSULE_PARENT = Path("/tmp/retrospective-complexity-05c-runs")
LOCK_PARENT = Path("/tmp/retrospective-complexity-05c-locks")
WORKSPACE = Path("/mnt/workspace")
CODEX_PACKAGE = Path("/home/dtopz/.local/lib/node_modules/@openai/codex")
CODEX_BIN_DIR = Path("/home/dtopz/.local/bin")
CODEX_AUTH = Path("/home/dtopz/.codex/auth.json")

DISABLED_FEATURES = (
    "apps",
    "auth_elicitation",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "goals",
    "hooks",
    "image_generation",
    "in_app_browser",
    "in_app_chat",
    "multi_agent",
    "plugins",
    "plugin_sharing",
    "remote_plugin",
    "skill_mcp_dependency_install",
    "skill_search",
    "standalone_web_search",
    "tool_suggest",
    "tool_call_mcp_elicitation",
    "view_image",
    "workspace_dependencies",
)


@contextmanager
def assessment_lock(number: int) -> Iterator[None]:
    LOCK_PARENT.mkdir(parents=True, exist_ok=True)
    path = LOCK_PARENT / f"amsterdam-eip-{number}.lock"
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StudyError(f"Another Task 05c session holds the EIP-{number} lock") from error
        yield


def dump_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def codex_version(codex: str) -> str:
    result = subprocess.run(
        [codex, "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode:
        raise StudyError("Unable to record Codex version")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise StudyError("Codex version command returned no value")
    return lines[-1]


def stage_capsule(number: int) -> tuple[Path, str, Path]:
    package = PACKAGE_ROOT / f"eip-{number}"
    manifest = load_yaml(package / "manifest.yaml")
    output = AUTOMATED_ROOT / f"eip-{number}.yaml"
    if output.exists():
        raise StudyError(f"Canonical output exists; refusing to overwrite: {output}")
    if int(manifest.get("eip", {}).get("number", -1)) != number:
        raise StudyError(f"Prepared package identity mismatch for EIP-{number}")
    template_source = load_yaml(package / "output-template.yaml")
    prompt_source = REPO_ROOT / template_source["provenance"]["assessor_prompt"]["path"]
    if not prompt_source.is_file():
        raise StudyError(f"Rendered prompt is missing for EIP-{number}")

    run_id = f"assessment-run-{uuid.uuid4()}"
    CAPSULE_PARENT.mkdir(parents=True, exist_ok=True)
    capsule = Path(
        tempfile.mkdtemp(
            prefix=f"amsterdam-eip-{number}-{run_id.removeprefix('assessment-run-')}-",
            dir=CAPSULE_PARENT,
        )
    )
    shutil.copy2(CONTRACT_PATH, capsule / "ASSESSMENT-CONTRACT.md")
    shutil.copy2(prompt_source, capsule / "PROMPT.md")
    capsule_package = capsule / "package"
    capsule_package.mkdir()
    allowlist = [
        "manifest.yaml",
        "output-template.yaml",
        *manifest["assessment_source_files"],
    ]
    if len(allowlist) != len(set(allowlist)):
        raise StudyError(f"EIP-{number} capsule allowlist contains duplicates")
    for name in allowlist:
        source = package / name
        destination = capsule_package / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    runtime = Path(tempfile.mkdtemp(prefix="codex-05c-runtime-", dir=CAPSULE_PARENT))
    (runtime / "config.toml").write_text(
        """model = "gpt-5.6-sol"
model_reasoning_effort = "xhigh"
approval_policy = "never"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
writable_roots = ["/mnt/workspace"]

[shell_environment_policy]
inherit = "core"

[projects."/mnt/workspace"]
trust_level = "trusted"
""",
        encoding="utf-8",
    )

    codex = shutil.which("codex")
    if codex is None:
        raise StudyError("Codex executable was not found")
    template_path = capsule_package / "output-template.yaml"
    template = load_yaml(template_path)
    environment = template["provenance"]["assessor_environment"]
    environment["codex_executable_path"] = "/home/dtopz/.local/bin/codex"
    environment["codex_version"] = codex_version(codex)
    environment["codex_binary_sha256"] = sha256_file(Path(codex))
    environment["run_at"] = now()
    environment["session_id"] = run_id
    environment["session_id_source"] = "isolated_launcher_run_id"
    environment["isolation_method"] = ISOLATION_METHOD
    environment["command"] = codex_inner_command()
    dump_yaml(template_path, template)
    return capsule, run_id, runtime


def bubblewrap_prefix(capsule: Path, runtime: Path) -> list[str]:
    bwrap = shutil.which("bwrap")
    codex = shutil.which("codex")
    if bwrap is None:
        raise StudyError("bubblewrap is required but was not found")
    if codex is None or not CODEX_PACKAGE.is_dir() or not CODEX_BIN_DIR.is_dir():
        raise StudyError("The local Codex installation could not be resolved")
    if not CODEX_AUTH.is_file():
        raise StudyError(f"Codex authentication is missing: {CODEX_AUTH}")
    return [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-cgroup",
        "--ro-bind",
        "/",
        "/",
        "--tmpfs",
        "/home/dtopz",
        "--dir",
        "/home/dtopz/.local",
        "--dir",
        "/home/dtopz/.local/bin",
        "--ro-bind",
        str(CODEX_BIN_DIR),
        "/home/dtopz/.local/bin",
        "--dir",
        "/home/dtopz/.local/lib",
        "--dir",
        "/home/dtopz/.local/lib/node_modules",
        "--dir",
        "/home/dtopz/.local/lib/node_modules/@openai",
        "--ro-bind",
        str(CODEX_PACKAGE),
        "/home/dtopz/.local/lib/node_modules/@openai/codex",
        "--dir",
        "/home/dtopz/.codex",
        "--ro-bind",
        str(CODEX_AUTH),
        "/home/dtopz/.codex/auth.json",
        "--ro-bind",
        str(runtime / "config.toml"),
        "/home/dtopz/.codex/config.toml",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/mnt",
        "--dir",
        str(WORKSPACE),
        "--bind",
        str(capsule),
        str(WORKSPACE),
        "--proc",
        "/proc",
        "--dev-bind",
        "/dev",
        "/dev",
        "--chdir",
        str(WORKSPACE),
        "--setenv",
        "TMPDIR",
        "/tmp",
    ]


def codex_inner_command() -> list[str]:
    command = [
        "/home/dtopz/.local/bin/codex",
        "exec",
        "--strict-config",
        "-C",
        str(WORKSPACE),
        "-m",
        "gpt-5.6-sol",
        "-c",
        'model_reasoning_effort="xhigh"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-s",
        "workspace-write",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--color",
        "never",
    ]
    for feature in DISABLED_FEATURES:
        command.extend(("--disable", feature))
    command.append(
        "Read ASSESSMENT-CONTRACT.md and PROMPT.md completely, then follow them exactly. "
        "Work only on the assigned EIP and write only assessment.yaml."
    )
    return command


def codex_command(capsule: Path, runtime: Path) -> list[str]:
    return [*bubblewrap_prefix(capsule, runtime), "--", *codex_inner_command()]


def verify_isolation(capsule: Path, runtime: Path) -> None:
    filesystem_probe = r"""
from pathlib import Path

workspace = Path('/mnt/workspace')
assert {path.name for path in workspace.iterdir()} == {
    'ASSESSMENT-CONTRACT.md', 'PROMPT.md', 'package'
}
manifest = __import__('yaml').safe_load((workspace / 'package/manifest.yaml').read_text())
expected = {'manifest.yaml', 'output-template.yaml', *manifest['assessment_source_files']}
actual = {
    path.relative_to(workspace / 'package').as_posix()
    for path in (workspace / 'package').rglob('*') if path.is_file()
}
assert actual == expected, (actual, expected)
for path in (
    Path('/home/dtopz/code'),
    Path('/home/dtopz/.agents'),
    Path('/home/dtopz/.codex/history.jsonl'),
    Path('/tmp/retrospective-complexity-05c-runs'),
):
    assert not path.exists(), f'forbidden host path visible: {path}'
print('filesystem isolation verified: exact positive allowlist and hidden host state')
"""
    result = subprocess.run(
        [*bubblewrap_prefix(capsule, runtime), "--", "/usr/bin/python3", "-c", filesystem_probe],
        check=False,
    )
    if result.returncode:
        raise StudyError("Filesystem-isolation self-test failed")

    network_probe = r"""
import socket
try:
    socket.create_connection(('1.1.1.1', 443), timeout=0.25)
except OSError:
    print('direct network denied in Codex tool sandbox')
else:
    raise SystemExit('direct network unexpectedly available')
"""
    sandbox_state = {
        "permissionProfile": {
            "type": "managed",
            "file_system": {
                "type": "restricted",
                "entries": [
                    {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"},
                    {"path": {"type": "path", "path": str(WORKSPACE)}, "access": "write"},
                    {"path": {"type": "special", "value": {"kind": "slash_tmp"}}, "access": "write"},
                    {"path": {"type": "special", "value": {"kind": "tmpdir"}}, "access": "write"},
                ],
            },
            "network": "restricted",
        },
        "sandboxCwd": "file:///mnt/workspace",
    }
    sandbox_command = [
        *bubblewrap_prefix(capsule, runtime),
        "--",
        "/home/dtopz/.local/bin/codex",
        "sandbox",
        "--sandbox-state-json",
        json.dumps(sandbox_state, separators=(",", ":")),
        "--sandbox-state-disable-network",
        "--",
        "/usr/bin/python3",
        "-c",
        network_probe,
    ]
    result = subprocess.run(sandbox_command, check=False)
    if result.returncode:
        raise StudyError("Codex tool-sandbox network-denial self-test failed")

    config_probe = [
        *bubblewrap_prefix(capsule, runtime),
        "--",
        "/home/dtopz/.local/bin/codex",
        "--strict-config",
        "-C",
        str(WORKSPACE),
        "-c",
        'model_reasoning_effort="xhigh"',
        "-c",
        "sandbox_workspace_write.network_access=false",
    ]
    for feature in DISABLED_FEATURES:
        config_probe.extend(("--disable", feature))
    config_probe.append("--version")
    result = subprocess.run(config_probe, check=False)
    if result.returncode:
        raise StudyError("Codex rejected the locked-down feature configuration")
    exec_probe = codex_command(capsule, runtime)
    exec_probe[-1] = "--version"
    result = subprocess.run(exec_probe, check=False)
    if result.returncode:
        raise StudyError("Codex rejected the exact non-interactive assessor configuration")
    print(
        "isolation verified: filesystem hidden, direct tool network denied, approvals never, "
        "web/MCP/apps/plugins/skills/browser/multi-agent features disabled"
    )


def import_output(number: int, capsule: Path) -> Path:
    source = capsule / "assessment.yaml"
    if not source.is_file():
        raise StudyError(f"Assessor produced no assessment.yaml; retained capsule: {capsule}")
    validate_automated(number, source)
    destination = AUTOMATED_ROOT / f"eip-{number}.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            output.write(source.read_bytes())
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as error:
        raise StudyError(f"Refusing to overwrite canonical output: {destination}") from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if destination.exists():
            destination.unlink()
        raise
    validate_automated(number)
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument("--verify-isolation", action="store_true")
    parser.add_argument("--collect-capsule", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with assessment_lock(args.eip):
        if args.collect_capsule is not None:
            output = import_output(args.eip, args.collect_capsule.resolve())
            print(f"collected validated assessment: {output}")
            return 0
        capsule, run_id, runtime = stage_capsule(args.eip)
        try:
            print(f"staged isolated capsule: {capsule}")
            print(f"launcher session ID: {run_id}")
            if args.verify_isolation:
                verify_isolation(capsule, runtime)
                print("No assessor was launched and no canonical output was written.")
                return 0
            result = subprocess.run(codex_command(capsule, runtime), check=False)
            if result.returncode:
                raise StudyError(f"Codex exited with status {result.returncode}; capsule retained at {capsule}")
            output = import_output(args.eip, capsule)
            print(f"collected validated assessment: {output}")
            print(f"audit capsule retained at: {capsule}")
            return 0
        finally:
            shutil.rmtree(runtime, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"isolated launch error: {error}") from error
