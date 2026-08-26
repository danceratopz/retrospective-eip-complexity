#!/usr/bin/env python3
"""Run one Task 05 assessment in a filesystem-isolated one-EIP capsule."""

from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml

from mark_complete import CompletionError, checklist_path, tick
from validate_inputs import ValidationError as InputValidationError
from validate_inputs import validate_package
from validate_output import ValidationError as OutputValidationError
from validate_output import package_paths, validate


TASK_ROOT = Path(__file__).resolve().parents[1]
TASK_CONTRACT = TASK_ROOT / "TASK.md"
CONTRACT_CAPSULE_NAME = "TASK.md"
CAPSULE_PARENT = Path("/tmp/retrospective-complexity-assessment-runs")
LOCK_PARENT = Path("/tmp/retrospective-complexity-assessment-locks")
ISOLATION_METHOD = "bubblewrap_one_eip_capsule_v1"
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


class LaunchError(RuntimeError):
    """Raised when an isolated assessment cannot be safely launched or collected."""


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LaunchError(f"Expected a YAML mapping: {path}")
    return data


def dump_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


@contextmanager
def assessment_lock(fork_id: str, number: int) -> Iterator[None]:
    LOCK_PARENT.mkdir(parents=True, exist_ok=True)
    path = LOCK_PARENT / f"{fork_id}-eip-{number}.lock"
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise LaunchError(
                f"Another isolated session already holds the lock for {fork_id} EIP-{number}"
            ) from error
        yield


def stage_capsule(fork_id: str, number: int) -> tuple[Path, str, Path]:
    package, output_path, prompt_path, _ = package_paths(fork_id, number)
    if output_path.exists():
        raise LaunchError(
            f"Canonical output already exists; refusing to overwrite it: {output_path}"
        )
    if not package.is_dir() or not prompt_path.is_file():
        raise LaunchError(f"No prepared Task 05 input exists for {fork_id} EIP-{number}")
    validate_package(fork_id, package)

    run_id = f"assessment-run-{uuid.uuid4()}"
    CAPSULE_PARENT.mkdir(parents=True, exist_ok=True)
    capsule = Path(
        tempfile.mkdtemp(
            prefix=f"{fork_id}-eip-{number}-{run_id.removeprefix('assessment-run-')}-",
            dir=CAPSULE_PARENT,
        )
    )
    shutil.copy2(TASK_CONTRACT, capsule / CONTRACT_CAPSULE_NAME)
    shutil.copy2(prompt_path, capsule / "PROMPT.md")
    shutil.copytree(package, capsule / "package")

    template_path = capsule / "package" / "output-template.yaml"
    template = load_yaml(template_path)
    assessor = template["provenance"]["assessor"]
    assessor["session_id"] = run_id
    assessor["session_id_source"] = "isolated_launcher_run_id"
    assessor["isolation_method"] = ISOLATION_METHOD
    dump_yaml(template_path, template)

    runtime = Path(tempfile.mkdtemp(prefix="codex-runtime-", dir=CAPSULE_PARENT))
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
    return capsule, run_id, runtime


def bubblewrap_prefix(capsule: Path, runtime: Path) -> list[str]:
    bwrap = shutil.which("bwrap")
    codex = shutil.which("codex")
    if bwrap is None:
        raise LaunchError("bubblewrap is required but bwrap was not found")
    if codex is None or not CODEX_PACKAGE.is_dir() or not CODEX_BIN_DIR.is_dir():
        raise LaunchError("The local Codex installation could not be resolved")
    if not CODEX_AUTH.is_file():
        raise LaunchError(f"Codex authentication is missing: {CODEX_AUTH}")

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


def codex_command(
    capsule: Path,
    runtime: Path,
    *,
    interactive: bool = False,
) -> list[str]:
    command = [
        *bubblewrap_prefix(capsule, runtime),
        "--",
        "/home/dtopz/.local/bin/codex",
    ]
    if not interactive:
        command.append("exec")
    command.extend(
        [
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
        ]
    )
    if interactive:
        command.extend(("-a", "never", "--no-alt-screen"))
    else:
        command.extend(
            (
                "--ephemeral",
                "--skip-git-repo-check",
                "--ignore-rules",
                "--color",
                "never",
            )
        )
    for feature in DISABLED_FEATURES:
        command.extend(("--disable", feature))
    command.append(
        "Read PROMPT.md and follow it exactly. Work only on the assigned EIP. "
        "Internet access and all external information sources are forbidden."
    )
    return command


def verify_isolation(capsule: Path, runtime: Path) -> None:
    code = f"""
from pathlib import Path

required = [
    Path('/mnt/workspace/{CONTRACT_CAPSULE_NAME}'),
    Path('/mnt/workspace/PROMPT.md'),
    Path('/mnt/workspace/package/manifest.yaml'),
]
for path in required:
    assert path.is_file(), f'missing capsule input: {{path}}'
for path in (
    Path('/home/dtopz/code'),
    Path('/home/dtopz/.agents'),
    Path('/home/dtopz/.codex/history.jsonl'),
    Path('/tmp/retrospective-complexity-assessment-runs'),
):
    assert not path.exists(), f'forbidden host path is visible: {{path}}'
package_dirs = [path for path in Path('/mnt/workspace/package').iterdir() if path.is_dir()]
assert all(path.name == 'supporting' for path in package_dirs)
print('filesystem isolation verified: one EIP capsule visible; host home and prior runs hidden')
"""
    command = [
        *bubblewrap_prefix(capsule, runtime),
        "--",
        "/usr/bin/python3",
        "-c",
        code,
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise LaunchError("Filesystem-isolation self-test failed")

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
        raise LaunchError("Codex rejected the locked-down assessor configuration")

    trust_probe = [
        *bubblewrap_prefix(capsule, runtime),
        "--",
        "/home/dtopz/.local/bin/codex",
        "-C",
        str(WORKSPACE),
    ]
    for feature in DISABLED_FEATURES:
        trust_probe.extend(("--disable", feature))
    trust_probe.extend(("debug", "prompt-input", "isolated trust probe"))
    result = subprocess.run(
        trust_probe,
        check=False,
        stdout=subprocess.DEVNULL,
    )
    if result.returncode:
        raise LaunchError("Codex did not accept the capsule as a trusted project")

    exec_probe = codex_command(capsule, runtime)
    exec_probe[-1] = "--version"
    result = subprocess.run(exec_probe, check=False)
    if result.returncode:
        raise LaunchError("Codex rejected the non-interactive assessor command")
    print(
        "assessor configuration verified: capsule trusted, non-interactive execution ready, "
        "internet tools disabled, shell network disabled, approvals disabled"
    )


def import_output(fork_id: str, number: int, capsule: Path) -> Path:
    capsule_output = capsule / "assessment.yaml"
    if not capsule_output.is_file():
        raise LaunchError(
            "Codex exited without producing assessment.yaml; no output was imported and "
            f"the audit capsule was retained at {capsule}"
        )
    validate(fork_id, number, output_override=capsule_output)
    _, canonical_output, _, _ = package_paths(fork_id, number)
    canonical_output.parent.mkdir(parents=True, exist_ok=True)
    payload = capsule_output.read_bytes()
    descriptor: int | None = None
    try:
        descriptor = os.open(
            canonical_output,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        with os.fdopen(descriptor, "wb") as destination:
            descriptor = None
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError as error:
        raise LaunchError(f"Refusing to overwrite canonical output: {canonical_output}") from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if canonical_output.exists():
            canonical_output.unlink()
        raise

    validate(fork_id, number)
    tick(checklist_path(fork_id), number)
    return canonical_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument(
        "--verify-isolation",
        action="store_true",
        help="stage a capsule and test its filesystem boundary without launching Codex",
    )
    parser.add_argument(
        "--collect-capsule",
        type=Path,
        help="validate and collect an existing interrupted capsule without launching Codex",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="use the Codex TUI instead of the default non-interactive execution",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with assessment_lock(args.fork, args.eip):
        if args.collect_capsule is not None:
            output = import_output(args.fork, args.eip, args.collect_capsule.resolve())
            print(f"collected validated assessment: {output}")
            return 0
        capsule, run_id, runtime = stage_capsule(args.fork, args.eip)
        try:
            print(f"staged isolated capsule: {capsule}")
            print(f"launcher session ID: {run_id}")
            if args.verify_isolation:
                verify_isolation(capsule, runtime)
                print("No assessor was launched and no canonical output was written.")
                return 0

            result = subprocess.run(
                codex_command(capsule, runtime, interactive=args.interactive),
                check=False,
            )
            if result.returncode:
                raise LaunchError(
                    f"Codex exited with status {result.returncode}; capsule retained at {capsule}"
                )
            output = import_output(args.fork, args.eip, capsule)
            print(f"collected validated assessment: {output}")
            print(f"audit capsule retained at: {capsule}")
            return 0
        finally:
            shutil.rmtree(runtime, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LaunchError,
        InputValidationError,
        OutputValidationError,
        CompletionError,
    ) as error:
        raise SystemExit(f"isolated launch error: {error}") from error
