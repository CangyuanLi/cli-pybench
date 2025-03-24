import argparse
from importlib.metadata import version

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
        "-v",
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=version("cli-pybench")),
        help="Displays package version",
    )

    return parser


def main():
    args = get_parser().parse_args()

    bench = Bench(args.benchpath)
    bench.run()

    if not args.no_save:
        bench.save_results()

    if args.print:
        print(
            bench.results.drop(
                "available_cpus",
                "available_ram",
                "platform",
                "processor",
                "branch",
                "commit",
                "version",
                "timestamp",
                "repeat",
                "number",
                "warmups",
                "garbage_collection",
                "median",
                "std",
                "p5",
                "p95",
                "p1",
                "p99",
                strict=False,
            ).sort("function", "parameters")
        )


if __name__ == "__main__":
    main()
