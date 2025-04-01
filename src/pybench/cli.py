import argparse
import json
import re
from importlib.metadata import version

import polars as pl

from ._bench import Bench


def get_parser():
    parser = argparse.ArgumentParser(description="Generate python project")

    parser.add_argument(
        "benchpath",
        type=str,
        nargs="?",
        default=None,
        help="path to benchmark file or folder",
    )

    parser.add_argument(
        "-n", "--no-save", action="store_true", help="disable saving of results"
    )

    parser.add_argument(
        "-p", "--print", action="store_true", help="print out latest run"
    )

    parser.add_argument(
        "-k",
        "--keyword",
        type=str,
        default=None,
        help="specify a regex to control what benchmark functions are run",
    )

    parser.add_argument(
        "--metadata", type=str, help="extra metadata to store in each run", default=None
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=version("cli-pybench")),
        help="Displays package version",
    )

    return parser


def _collapse_units(s: str) -> str:
    parts = s.split(" ")
    if len(parts) <= 1:
        return s

    new_parts = []
    for p in parts:
        num = []
        unit = []
        for c in p:
            if c.isdigit():
                num.append(c)
            else:
                unit.append(c)

        num = "".join(num)
        unit = "".join(unit)

        new_parts.append((num, unit))

    p1, p2 = new_parts

    if p1[1] in ("h", "m"):
        return s

    return f"{p1[0]}.{p2[0].zfill(3)}{p1[1]}"


def readable_duration(seconds: float, parts_count: int = 2) -> str:
    # https://stackoverflow.com/questions/26164671/convert-seconds-to-readable-format-time
    """Returns readable time span out of number of seconds. No rounding."""

    parts_with_units = [
        (60 * 60, "h"),
        (60, "m"),
        (1, "s"),
        (1e-3, "ms"),
        (1e-6, "us"),
        (1e-9, "ns"),
    ]
    info = ""
    remaining = abs(seconds)
    for time_part, unit in parts_with_units:
        partial_amount = int(remaining // time_part)
        if partial_amount:
            optional_space = " " if info else ""
            info += f"{optional_space}{partial_amount}{unit}"
            remaining %= time_part
            parts_count -= 1
        if not parts_count:
            break
    if not info and seconds != 0:
        return "~0s"

    return _collapse_units(info) or "0s"


def main():
    args = get_parser().parse_args()

    bench = Bench(args.benchpath)
    bench.run(
        keyword_regex=None if args.keyword is None else re.compile(args.keyword),
        extra_metadata=None if args.metadata is None else json.loads(args.metadata),
    )

    if not args.no_save:
        bench.save_results()

    if args.print:
        display_df = bench.results.select(
            "function",
            "parameters",
            pl.col("mean", "min", "median", "p5", "p95").map_elements(
                readable_duration, return_dtype=pl.String
            ),
        )

        if display_df["parameters"].is_null().all():
            display_df = display_df.drop("parameters").sort("function")
        else:
            display_df = display_df.sort("function", "parameters")

        with pl.Config(set_tbl_rows=-1, set_tbl_hide_column_data_types=True):
            print(display_df)


if __name__ == "__main__":
    main()
