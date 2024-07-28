# pybench:
[![PyPI version](https://badge.fury.io/py/cli-pybench.svg)](https://badge.fury.io/py/cli-pybench)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cli-pybench)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Tests](https://github.com/CangyuanLi/cli-pybench/actions/workflows/tests.yml/badge.svg)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

## What is it?

**pybench** is a simple benchmarking framework that mimics **pytest** syntax. Simply write create files beginning with "bench_" and **pybench** will discover those files and benchmark all functions starting with "bench_". Internally, **pybench** relies on Python's standard **timeit** library to produce benchmark statistics. These statistics, along with metadata such as your platform, available CPUs, RAM, project version, commit id, and more, are stored in a parquet file for further analysis. That way, you have access to the raw data necessary to track performance over time and commits, identify regressions, and any other analysis you may want to do.

# Usage:

## Dependencies

- polars
- toml
- tqdm

## Installing

The easiest way is to install **cli-pybench** is from PyPI using pip:

```sh
pip install cli-pybench
```

## Quickstart

Installing the library will expose a `pybench` command in your terminal. Although the benchmark directory is configurable, by convention, create a folder called "benchmarks" in your project root. Then, create a file prefixed with "bench_". In that file, write a function starting with "bench_".

```python
def bench_my_sum():
    return 1 + 1
```

Then, simply run `pybench` from your terminal! It should look something like this:

```
starting benchmark session ...
default config: Config(benchpath='benchmarks', repeat=30, number=1, warmups=0, garbage_collection=False)
running on Linux-5.15.123.1-microsoft-standard-WSL2-x86_64-with-glibc2.35 with x86_64, available cpus: 16, RAM: 10.05GB

/home/cangyuanli/Documents/Projects/cli-pybench/benchmarks/bench_pybench.py
100%|██████████████████████████████████████████████████████████████████████████████████████████████████| 6/6 [00:00<00:00, 184.31it/s]
```

Then, a "results.parquet" file will appear in your "benchmarks/" folder. If you want to change your configuration, you can do it globally through your "pyproject.toml" file like so:

```
[tool.pybench]
repeat = 100
number = 10
warmups = 1
```

To learn more about the `repeat` and `number` parameters, see the documentation for `timeit.repeat` here: https://docs.python.org/3/library/timeit.html.

You can also change your configuration for a specific function through the `pybench.config` decorator. Here's an example:

```python
import pybench

@pybench.config(repeat=1_000, number=100)
def bench_my_sum():
    return 1 + 1
```

**pybench** provides two other decorators. One is the `pybench.skipif` decorator. It simply skips the function if the input evaluates to True. This is useful for a variety of reasons, for example, if you have a long-running benchmark that you do not want to run frequently. of course, all decorators can be combined.

```python
import pybench

@pybench.config(repeat=1_000, number=100)
@pybench.skipif(True)
def bench_my_sum():
    1 + 1
```

The final decorator is the `pybench.parametrize` decorator. This benchmarks your function for each input in a given list of inputs. There are two syntaxes for this. The first is the dictionary syntax.

```python
import pybench

@pybench.parametrize({"a": [1, 2], "b": [5, 8, 9]})
def bench_my_sum(a, b):
    a + b
```

This will benchmark `bench_my_sum` for the product of "a" and "b". Users of **pytest** may be more familiar with the second syntax.

```python
import pybench

@pybench.parametrize(("a", "b"), [(1, 2), (3, 4)])
def bench_my_sum(a, b):
    a + b
```
