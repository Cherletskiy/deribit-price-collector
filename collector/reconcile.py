import argparse

from app.core.config import config
from collector.tasks import reconcile_recent_prices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ticker",
        dest="tickers",
        action="append",
        help="Ticker to reconcile. Repeat for multiple tickers.",
    )
    parser.add_argument(
        "--lookback-seconds",
        dest="lookback_seconds",
        type=int,
        default=config.RECONCILIATION_LOOKBACK_SEC,
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    tickers = args.tickers or list(config.supported_tickers)
    reconcile_recent_prices(
        tickers=tickers,
        lookback_seconds=args.lookback_seconds,
    )


if __name__ == "__main__":
    main()
