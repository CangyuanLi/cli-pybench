from ._bench import Bench


def main():
    bench = Bench()
    bench.run()
    bench.save_results()


if __name__ == "__main__":
    main()
