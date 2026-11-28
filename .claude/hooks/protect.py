"""PreToolUse hook: block access to secrets and risky git commands.

Claude Code sends the pending tool call as JSON on stdin.
Exit code 2 blocks the call, and the message on stderr goes back to Claude.
Exit code 0 allows the call.

This is a guardrail, not a security boundary. It catches mistakes.
The permissions "deny" list in settings.json is a second layer.
"""

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath

# Claude Code sets this to the project root, even if Claude has run `cd`.
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or None

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# (pattern, message) pairs for shell commands.
GIT_RULES = [
    (
        r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f\b)",
        "Force push is blocked.",
    ),
    (
        r"\bgit\s+push\b.*\bmain\b",
        "Push to main is blocked. Push a feature branch and open a pull request.",
    ),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard is blocked. Ask TJ first."),
    (r"\bgit\s+clean\b.*\s-[a-zA-Z]*f", "git clean -f is blocked. Ask TJ first."),
    (r"--no-verify\b", "Skipping git hooks with --no-verify is blocked."),
]


# Directories that hold credentials, usually under the home directory.
SECRET_DIRS = (".ssh", ".aws", ".kube", ".docker")

# One example of each kind of secret file name. A wildcard such as `.en?`
# is blocked if it could expand to any of these.
SECRET_NAME_EXAMPLES = (
    ".env",
    ".env.local",
    ".git-credentials",
    "server.pem",
    "server.key",
    "cert.pfx",
    "cert.p12",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
)

# PowerShell drives that expose environment variables, session variables,
# functions, the registry, and certificates. Two spellings:
#   drive:     `Env:`, also after a parameter colon or a slash (`-Path:Env:`)
#   provider:  `Environment::`, `Microsoft.PowerShell.Core\Registry::HKCU`
# `$env:NAME` and `${env:NAME}` have `$` or `{` before `env`, so they pass.
PROVIDER_PATH = re.compile(
    r"(?:^|[:\\/])(?:env|variable|function|hkcu|hklm|cert):"
    r"|(?:environment|variable|function|registry|certificate|alias)::",
    re.IGNORECASE,
)

# Bash brace expansion: `{a,b}` or `{a..z}`. Each group is replaced by `*`.
# That can only widen what matches, so the check fails closed.
BRACE_GROUP = re.compile(r"\{[^{}]*(?:,|\.\.)[^{}]*\}")


def to_fnmatch(text: str) -> str:
    """Rewrite bash glob syntax that fnmatch reads differently."""
    text = BRACE_GROUP.sub("*", text)
    # Bash accepts `[^x]` for "not x"; fnmatch only understands `[!x]`.
    return text.replace("[^", "[!")


def has_wildcard(text: str) -> bool:
    return any(char in text for char in "*?[")


def could_match(part: str, names: tuple[str, ...]) -> bool:
    """True if `part` is one of `names`, or is a wildcard that matches one."""
    if has_wildcard(part):
        return any(fnmatch.fnmatchcase(name, part) for name in names)
    return part in names


def is_secret_name(name: str) -> bool:
    if name in (".env", ".git-credentials"):
        return True
    if name.startswith(".env.") and not name.endswith(".example"):
        return True
    if name.endswith((".pem", ".key", ".pfx", ".p12")):
        return True
    return name.startswith(("id_rsa", "id_ed25519", "id_ecdsa"))


def is_secret_path(text: str) -> bool:
    """Return True if a path looks like a secret file, or a wildcard could reach one."""
    path = PurePosixPath(to_fnmatch(text).replace("\\", "/"))
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]

    if is_secret_name(name):
        return True
    if has_wildcard(name) and could_match(name, SECRET_NAME_EXAMPLES):
        return True
    return any(could_match(part, SECRET_DIRS) for part in parts)


def current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,  # Outside a repo, stdout is empty and we return "".
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_DIR,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def block(message: str) -> None:
    print(f"BLOCKED by .claude/hooks/protect.py: {message}", file=sys.stderr)
    sys.exit(2)


def check_shell(command: str) -> None:
    # Split on whitespace and shell punctuation, then check each piece as a path.
    for token in re.split(r"[\s'\"=<>|;&()]+", command):
        if not token:
            continue
        if is_secret_path(token):
            block(f"The command touches a secret file ({token}).")
        if PROVIDER_PATH.search(token):
            block(f"PowerShell provider paths like {token} are blocked.")

    for pattern, message in GIT_RULES:
        if re.search(pattern, command):
            block(message)

    if re.search(r"\bgit\s+push\b", command) and current_branch() == "main":
        block("You are on main. Create a feature branch before you push.")


def check_file_tool(tool_input: dict) -> None:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and is_secret_path(value):
            block(f"Access to secret file {value} is not allowed.")


def main() -> None:
    data = json.loads(sys.stdin.buffer.read() or b"{}")
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    if tool in SHELL_TOOLS:
        check_shell(tool_input.get("command", ""))
    elif tool in FILE_TOOLS:
        check_file_tool(tool_input)

    sys.exit(0)


if __name__ == "__main__":
    main()
