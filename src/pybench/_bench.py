import ast
import dataclasses
import importlib.util
import inspect
import json
import timeit
from pathlib import Path
from typing import Optional

import polars as pl
import toml
import tqdm

from ._metadata import _get_branch_name, _get_commit_id, _get_time, _get_version


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
    def __init__(self, benchpath: Optional[Path] = None):
        self.rootdir = self.get_rootdir()
        self.config = self.load_config()

        self.benchpath = (
            self.rootdir / self.config.benchpath if benchpath is None else benchpath
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
        timing_dfs = []
        config_dfs = []
        metadata_df = pl.LazyFrame(
            {
                "meta_join_id": True,
                "timestamp": _get_time(),
                "branch": _get_branch_name(),
                "commit": _get_commit_id(),
                "version": _get_version(self.rootdir),
            }
        )

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
                decorators = get_decorators(func)

                is_parametrized = False
                for decorator in decorators[func_name]:
                    if decorator == "parametrize":
                        is_parametrized = True

                real_func = func()

                if hasattr(real_func, "_skip") and real_func._skip:
                    continue

                if hasattr(real_func, "_config"):
                    config = real_func._config | self.config.__dict__

                else:
                    config = self.config.__dict__

                setup = "gc.enable()" if config["garbage_collection"] else "pass"

                config_dfs.append(
                    pl.LazyFrame(config).with_columns(
                        pl.lit(func_name).alias("function")
                    )
                )

                fs = [real_func] if not is_parametrized else real_func()

                for f in fs:
                    args = get_default_args(f)
                    for _ in range(config["warmups"]):
                        pass
                    timings = timeit.repeat(
                        f,
                        setup=setup,
                        repeat=config["repeat"],
                        number=config["number"],
                    )

                    timing_dfs.append(
                        pl.LazyFrame(
                            {
                                "function": func_name,
                                "time": timings,
                                "parameters": json.dumps(args),
                            }
                        )
                    )

        if not timing_dfs:
            raise SystemExit("No benchmarks ran")

        timing_df: pl.LazyFrame = pl.concat(timing_dfs)
        config_df: pl.LazyFrame = pl.concat(config_dfs)

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
            .collect()
        )

        self.results = df

    def save_results(self):
        res: pl.DataFrame = pl.concat(
            [self.load_results(), self.results], how="vertical"
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
