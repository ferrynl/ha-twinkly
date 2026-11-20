"""Build and smoke-test both variants of the add-on."""
import os
import subprocess
import sys
from pathlib import Path

import yaml

from prepare_release import prepare


def main():
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-v"], check=True)
    source = Path("twinkly")
    version = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))["version"]
    for name, release, port in (("twinkly", version, "18489"), ("twinkly_beta", f"{version}-beta.1", "18491")):
        target = Path(os.environ["RUNNER_TEMP"]) / name
        prepare(source, target, release)
        subprocess.run(["bash", "scripts/smoke.sh", str(target), port], check=True)


if __name__ == "__main__":
    main()
