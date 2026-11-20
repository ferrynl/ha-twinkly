"""Publish the validated GitHub Actions checkout to the requested channel."""
import os
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from prepare_release import prepare


def main():
    source = Path("twinkly")
    version = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))["version"]
    push = os.environ["GITHUB_EVENT_NAME"] == "push"
    if push and version != "0.1.44":
        return
    beta = not push and os.environ.get("CHANNEL") == "beta"
    if beta:
        number = os.environ.get("BETA_NUMBER", "")
        if not re.fullmatch(r"[1-9][0-9]*", number):
            raise ValueError("Ongeldig bètanummer")
        version = f"{version}-beta.{number}"

    tag = f"v{version}"
    remote = subprocess.run(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"])
    if remote.returncode == 0:
        if push and subprocess.run(["gh", "release", "view", tag], stdout=subprocess.DEVNULL).returncode == 0:
            return
        raise RuntimeError(f"Tag {tag} bestaat al. Kies een nieuwe versie.")
    if remote.returncode != 2:
        remote.check_returncode()

    changelog = (source / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = changelog.split("\n# ", 1)[0].partition("\n")[2].strip()
    if not notes:
        raise ValueError("De release-opmerkingen ontbreken")

    with TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as temporary:
        directory = Path(temporary)
        prepare(source, directory / "release", version)
        notes_file = directory / "notes.md"
        notes_file.write_text(notes + "\n", encoding="utf-8")
        flags = ["--prerelease", "--latest=false"] if beta else ["--latest"]
        subprocess.run(
            ["gh", "release", "create", tag, "--target", os.environ["GITHUB_SHA"],
             "--title", f"Christmas Control Center {version}", "--notes-file", str(notes_file), *flags],
            check=True,
        )


if __name__ == "__main__":
    main()
