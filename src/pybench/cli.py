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
    bench.save_results()


if __name__ == "__main__":
    main()
