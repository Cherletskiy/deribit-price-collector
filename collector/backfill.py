import argparse

from app.core.config import config
from collector.providers import HistoryRange
from collector.tasks import backfill_price_history


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ticker",
        dest="tickers",
        action="append",
        help="Ticker to backfill. Repeat for multiple tickers.",
    )
    parser.add_argument(
        "--range",
        dest="range_name",
        choices=[item.value for item in HistoryRange],
        required=True,
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    tickers = args.tickers or list(config.supported_tickers)
    backfill_price_history(tickers=tickers, range_name=args.range_name)


if __name__ == "__main__":
    main()
