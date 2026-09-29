"""Entrypoint: ``python -m collector.run --registry /etc/kops/collectors.yaml``."""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=os.getenv("KOPS_COLLECTOR_REGISTRY", "/etc/kops/collectors.yaml"))
    parser.add_argument("--port", type=int, default=int(os.getenv("KOPS_COLLECTOR_PORT", "8091")))
    args = parser.parse_args()
    os.environ["KOPS_COLLECTOR_REGISTRY"] = args.registry
    os.environ["KOPS_COLLECTOR_PORT"] = str(args.port)

    from collector.server import main as serve

    serve()


if __name__ == "__main__":
    main()
