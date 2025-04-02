import ast
import dataclasses
import functools
import importlib.util
import inspect
import json
import re
import shutil
import sys
import timeit
from pathlib import Path
from typing import Any, Optional, Union

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
    partition_by: list[str] = dataclasses.field(default_factory=lambda: ["commit"])


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
    def __init__(
        self,
        benchpath: Optional[PathLike] = None,
    ):
        self.rootdir = self.get_rootdir()
        self.config = self.load_config()

        self.benchpath = (
            self.rootdir / self.config.benchpath
            if benchpath is None
            else Path(benchpath)
        )
        self.benchdir = Path(self.config.benchpath) / "results"
        self.benchdir.mkdir(exist_ok=True, parents=True)

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

    def run(
        self,
        keyword_regex: Optional[str] = None,
        extra_metadata: Optional[dict[str, Any]] = None,
    ):
        print("starting benchmark session ...")
        print(f"default config: {self.config}")

        if extra_metadata is None:
            extra_metadata = {}

        self._metadata = {
            "meta_join_id": True,
            "timestamp": _get_time(),
            "branch": _get_branch_name(),
            "commit": _get_commit_id(),
            "version": _get_version(self.rootdir),
            "python_version": sys.version,
            "available_cpus": _get_available_cpus(),
            "available_ram": _get_available_ram(),
            "platform": _get_platform(),
            "processor": _get_processor(),
        } | extra_metadata

        metadata = self._metadata

        print(
            f"running on {metadata["platform"]}, python {metadata["python_version"].split(" ")[0]}, available cpus: {metadata["available_cpus"]}, RAM: {metadata["available_ram"]}"
        )
        for k, v in extra_metadata.items():
            print(f"\t{k}: {v}")

        timing_dfs = []
        configs = []
        per_function_metadata_list = []
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
                    func_name = name[6:]  # remove the starting bench_

                    if keyword_regex is not None:
                        if not re.match(keyword_regex, func_name):
                            continue

                    funcs.append((func_name, obj))

            for func_name, func in tqdm.tqdm(funcs):
                if hasattr(func, "_skip") and func._skip:
                    continue

                if hasattr(func, "_metadata"):
                    per_function_metadata = func._metadata
                else:
                    per_function_metadata = {}

                per_function_metadata["function"] = func_name
                per_function_metadata_list.append(per_function_metadata)

                if hasattr(func, "_config"):
                    config = self.config.__dict__ | func._config
                else:
                    config = self.config.__dict__.copy()

                setup = "gc.enable()" if config["garbage_collection"] else "pass"

                config["function"] = func_name
                configs.append(config)

                if hasattr(func, "_params"):
                    fs = []
                    for params in func._params:
                        if func._setup is None:
                            part = functools.partial(func, **params)
                        else:
                            part = functools.partial(func, **func._setup(**params))

                        part._params = params
                        fs.append(part)
                else:
                    fs = [func]

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
        config_df: pl.LazyFrame = pl.LazyFrame(configs).drop(
            "benchpath", "partition_by", strict=False
        )
        per_function_metadata_df: pl.LazyFrame = pl.LazyFrame(
            per_function_metadata_list
        )

        df = (
            timing_df.group_by("function", "parameters")
            .agg(
                pl.col("time").mean().alias("mean"),
                pl.col("time").min().alias("min"),
                pl.col("time").max().alias("max"),
                pl.col("time").median().alias("median"),
                pl.col("time").std().alias("std"),
                pl.col("time").quantile(0.05).alias("p5"),
                pl.col("time").quantile(0.95).alias("p95"),
                pl.col("time").quantile(0.01).alias("p1"),
                pl.col("time").quantile(0.99).alias("p99"),
            )
            .join(config_df, on="function", how="left", validate="m:1")
            .join(per_function_metadata_df, on="function", how="left", validate="m:1")
            .with_columns(pl.lit(True).alias("meta_join_id"))
            .join(metadata_df, on="meta_join_id", how="left", validate="m:1")
            .drop("meta_join_id")
            .collect()
        )

        self.results = df

    def save_results(self):
        save_dir = self.benchdir / "historical"
        for key in self.config.partition_by:
            save_dir = save_dir / f"{key}={self._metadata[key]}"
        save_path = save_dir / "results.parquet"
        save_dir.mkdir(parents=True, exist_ok=True)

        self.results.write_parquet(save_path)
        shutil.copy(src=save_path, dst=self.benchdir / "results.parquet")

    def load_config(self):
        with open(self.rootdir / "pyproject.toml") as f:
            try:
                return Config(**toml.load(f)["tool"]["pybench"])
            except KeyError:
                return Config()
