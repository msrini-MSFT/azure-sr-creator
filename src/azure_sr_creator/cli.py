from __future__ import annotations

import argparse
import sys
from pathlib import Path

from azure.core.exceptions import ClientAuthenticationError

from .client import AzureSupportClient, AzureSupportError
from .workflow import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construct or submit an Azure Support REST API request."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--test",
        action="store_true",
        help="Construct and save the payload without creating an SR (default).",
    )
    mode.add_argument(
        "--create",
        action="store_true",
        help="Create a real Azure Support request after explicit confirmation.",
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
    parser.add_argument(
        "--ticket-name",
        help="ARM resource name for the ticket. Used only with --create; generated if omitted.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.ticket_name and not args.create:
        parser.error("--ticket-name requires --create")
    try:
        run_workflow(
            AzureSupportClient(),
            subscription=args.subscription,
            output=args.output,
            create=args.create,
            ticket_name=args.ticket_name,
        )
    except (AzureSupportError, ClientAuthenticationError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
