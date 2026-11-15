"""Prepare the two HA install variants from one source checkout."""
import argparse
import re
import shutil
from pathlib import Path

import yaml


def prepare(source, target, version):
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-beta\.([1-9][0-9]*))?", version)
    if not match:
        raise ValueError(f"Invalid release version: {version}")
    config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    if config["version"] != version.split("-")[0] or config["slug"] != "twinkly_kerst":
        raise ValueError("Release version or stable slug does not match config.yaml")

    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    beta_branding = target / "beta_branding"
    if match[4]:
        for filename in ("icon.png", "logo.png", "README.md"):
            (beta_branding / filename).replace(target / filename)
    shutil.rmtree(beta_branding)
    if not match[4]:
        return

    config.update(
        name="Twinkly Control Center Beta",
        slug="twinkly_kerst_beta",
        version=version,
        description="Probeer als eerste nieuwe Twinkly-lichtshows en muziekeffecten.",
        boot="manual",
        ingress_port=18491,
    )
    (target / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    dockerfile = target / "Dockerfile"
    lines = dockerfile.read_text(encoding="utf-8")
    dockerfile.write_text("".join([
        lines, "\nENV TWINKLY_HTTP_PORT=18491 TWINKLY_DDP_PORT=18492\n"
    ]), encoding="utf-8")
    changelog = target / "CHANGELOG.md"
    changelog.write_text(
        f"# {version}\n\nBètaversie van Twinkly Control Center.\n\n"
        + changelog.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()
    prepare(args.source, args.target, args.version)
