import pytest

from azure_sr_creator.cli import build_parser


def test_cli_defaults_to_test_mode() -> None:
    args = build_parser().parse_args([])

    assert args.create is False
    assert args.test is False


def test_cli_enables_create_mode() -> None:
    args = build_parser().parse_args(["--create", "--ticket-name", "sr-test"])

    assert args.create is True
    assert args.ticket_name == "sr-test"


def test_cli_rejects_both_modes() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--test", "--create"])
