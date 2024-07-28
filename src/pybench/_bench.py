import ast
import dataclasses
import importlib.util
import inspect
import json
import timeit
from pathlib import Path
from typing import Optional, Union

import polars as pl
import toml
import tqdm

from ._metadata import (
    _get_available_cpus,
    _get_available_ram,
    _get_branch_name,
    _get_commit_id,
    _get_platform,
    _get_processor,
    _get_time,
    _get_version,
)

PathLike = Union[Path, str]


@dataclasses.dataclass
class Config:
    benchpath: str = "benchmarks"
    repeat: int = 30
    number: int = 1
    warmups: int = 0
    garbage_collection: bool = False


def get_decorators(cls):
    target = cls
    decorators = {}

    def visit_function_def(node):
        decorators[node.name] = []
        for n in node.decorator_list:
            name = ""
            if isinstance(n, ast.Call):
                name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            else:
                name = n.attr if isinstance(n, ast.Attribute) else n.id

            decorators[node.name].append(name)

    node_iter = ast.NodeVisitor()
    node_iter.visit_FunctionDef = visit_function_def
    node_iter.visit(ast.parse(inspect.getsource(target)))

    # This doesn't get the fully qualified name, e.g. @pybench.skipif -> skipif.
    # Not sure if getting the fully qualified name is possible.

    return decorators


def get_func_name(func) -> str:
    try:
        func_name = func.__name__
    except AttributeError:
        func_name = func.func.__name__

    return func_name


def get_default_args(func) -> dict:
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


class Bench:
    def __init__(self, benchpath: Optional[PathLike] = None):
        self.rootdir = self.get_rootdir()
        self.config = self.load_config()

        self.benchpath = (
            self.rootdir / self.config.benchpath
            if benchpath is None
            else Path(benchpath)
        )
        self.benchdir = Path(self.config.benchpath)

    @staticmethod
    def get_rootdir():
        return Path.cwd()

    def get_bench_files(self):
        if self.benchpath.is_dir():
            bench_files = []
            for root, dirs, files in self.benchpath.walk():
                for dir in dirs:
                    if dir == "__pycache__":
                        continue

                for file in files:
                    if file.startswith("bench_") and file[-3:] == ".py":
                        bench_files.append(root / file)
        else:
            bench_files = [self.benchpath]

        return bench_files

    def run(self):
        print("starting benchmark session ...")
        print(f"default config: {self.config}")

        metadata = {
            "meta_join_id": True,
            "timestamp": _get_time(),
            "branch": _get_branch_name(),
            "commit": _get_commit_id(),
            "version": _get_version(self.rootdir),
            "available_cpus": _get_available_cpus(),
            "available_ram": _get_available_ram(),
            "platform": _get_platform(),
            "processor": _get_processor(),
        }

        print(
            f"running on {metadata["platform"]} with {metadata["processor"]}, available cpus: {metadata["available_cpus"]}, RAM: {metadata["available_ram"]}"
        )
        timing_dfs = []
        configs = []
        metadata_df = pl.LazyFrame(metadata)

        for file in self.get_bench_files():
            print("")
            print(file)
            spec = importlib.util.spec_from_file_location("module", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            funcs = []
            for name, obj in module.__dict__.items():
                if name.startswith("bench_") and callable(obj):
                    funcs.append(obj)

            for func in tqdm.tqdm(funcs):
                func_name = func.__name__

                real_func = func()

                if hasattr(real_func, "_skip") and real_func._skip:
                    continue

                if hasattr(real_func, "_config"):
                    config = real_func._config | self.config.__dict__

                else:
                    config = self.config.__dict__.copy()

                setup = "gc.enable()" if config["garbage_collection"] else "pass"

                config["function"] = func_name[6:]  # remove the starting bench_
                configs.append(config)

                if hasattr(real_func, "_funcs"):
                    fs = real_func._funcs
                else:
                    fs = [real_func]

                for f in fs:
                    for _ in range(config["warmups"]):
                        f()

                    timings = timeit.repeat(
                        f,
                        setup=setup,
                        repeat=config["repeat"],
                        number=config["number"],
                    )

                    if hasattr(f, "_params"):
                        args = json.dumps(f._params)
                    else:
                        args = None

                    timing_dfs.append(
                        pl.LazyFrame(
                            {
                                "function": config["function"],
                                "time": timings,
                                "parameters": args,
                            },
                            schema={
                                "function": pl.String,
                                "time": pl.Float64,
                                "parameters": pl.String,
                            },
                        )
                    )

        if not timing_dfs:
            raise SystemExit("No benchmarks ran")

        timing_df: pl.LazyFrame = pl.concat(timing_dfs)
        config_df: pl.LazyFrame = pl.LazyFrame(configs)

        df = (
            timing_df.group_by("function", "parameters")
            .agg(
                pl.col("time").mean().alias("mean"),
                pl.col("time").min().alias("min"),
                pl.col("time").max().alias("max"),
                pl.col("time").median().alias("median"),
                pl.col("time").std().alias("std"),
            )
            .join(config_df, on="function", how="left", validate="m:1")
            .with_columns(pl.lit(True).alias("meta_join_id"))
            .join(metadata_df, on="meta_join_id", how="left", validate="m:1")
            .drop("benchpath", "meta_join_id")
        )

        self.results = df

    def save_results(self):
        res: pl.DataFrame = pl.concat(
            [self.load_results(), self.results], how="diagonal_relaxed"
        )

        res.write_parquet(self.benchdir / "results.parquet")

    def load_results(self):
        try:
            return pl.read_parquet(self.benchdir / "results.parquet")
        except FileNotFoundError:
            return pl.DataFrame()

    def load_config(self):
        with open(self.rootdir / "pyproject.toml") as f:
            try:
                return Config(**toml.load(f)["tool"]["pybench"])
            except KeyError:
                return Config()
