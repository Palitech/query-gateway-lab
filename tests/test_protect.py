"""Tests for the .claude/hooks/protect.py guardrail.

The hook isn't a package, so it is loaded from its file path.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

HOOK_PATH = Path(__file__).parents[1] / ".claude" / "hooks" / "protect.py"


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("protect", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


protect = load_hook()


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "config/.env.local",
        "C:\\Users\\someone\\.ssh\\config",
        "~/.ssh/known_hosts",
        "deploy/server.pem",
        "id_ed25519_personal",
        # Home credential stores.
        "~/.aws/credentials",
        "~/.kube/config",
        "~/.docker/config.json",
        "~/.git-credentials",
        # Wildcards that could expand to a secret file.
        ".en?",
        ".e*",
        "*",
        "*.pem",
        "~/.ss?/id_rsa",
        "~/.a*/credentials",
        # Bash negation `[^x]`, which fnmatch spells `[!x]`.
        ".en[^x]",
        # Bash brace expansion.
        ".{env,x}",
        "~/.{ssh,x}/config",
        ".e{a..z}v",
        # Nested braces need more than one replacement pass.
        ".{e{n,x}v,y}",
    ],
)
def test_secret_paths_are_detected(path: str) -> None:
    assert protect.is_secret_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "src/query_gateway/api.py",
        "docker/init.sql",
        "*.py",
        "tests/test_*.py",
        "README.md",
    ],
)
def test_ordinary_paths_are_allowed(path: str) -> None:
    assert not protect.is_secret_path(path)


@pytest.mark.parametrize(
    "command",
    [
        "Get-Content .en?",
        "cat ~/.aws/credentials",
        "Get-ChildItem Env:",
        "Get-Content env:POSTGRES_PASSWORD",
        "Get-Item Variable:\\PSVersionTable",
        "Get-ChildItem HKCU:\\Software",
        "Get-ChildItem Cert:\\CurrentUser\\My",
        "Get-ChildItem -Path:Env:",
        "Get-ChildItem Environment::",
        "Get-Item Microsoft.PowerShell.Core\\Registry::HKEY_CURRENT_USER",
        # PowerShell takes comma-separated path lists.
        "Get-ChildItem .,Env:",
        "Get-Content README.md,.env",
        # Brace groups are replaced before the command is split on commas.
        "cat .{env,x}",
        "cat .{e{n,x}v,y}",
        "git push --force origin feature",
        "git reset --hard HEAD~1",
        "git commit --no-verify -m wip",
    ],
)
def test_blocked_commands(command: str) -> None:
    with pytest.raises(SystemExit) as exc:
        protect.check_shell(command)
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "command",
    [
        "git status -sb",
        "uv run pytest --cov=query_gateway",
        "ruff check src/*.py",
        'Write-Output "$env:CLAUDE_PROJECT_DIR"',
        "Write-Output ${env:CLAUDE_PROJECT_DIR}",
        "Get-ChildItem src | ForEach-Object {$_.Name}",
        # Bash doesn't expand braces that contain spaces, e.g. jq objects.
        "gh pr view 3 --json title,state --jq '{title, state}'",
        "Get-Content .env.example",
    ],
)
def test_allowed_commands(command: str) -> None:
    assert protect.check_shell(command) is None
