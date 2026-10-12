from __future__ import annotations

import argparse
import sys
from pathlib import Path

from azure.core.exceptions import ClientAuthenticationError

from .client import AzureSupportClient, AzureSupportError
from .workflow import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactively construct an Azure Support REST API payload."
    )
    parser.add_argument(
        "--subscription",
        help="Exact Azure subscription name or ID. Omit to select interactively.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("final-payload.json"),
        help="JSON output path (default: final-payload.json).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        run_workflow(
            AzureSupportClient(),
            subscription=args.subscription,
            output=args.output,
        )
    except (AzureSupportError, ClientAuthenticationError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
