import functools
import itertools
from collections.abc import Iterable
from typing import Any, Callable, Optional, Union


def config(
    repeat: Optional[int] = None,
    number: Optional[int] = None,
    warmups: Optional[int] = None,
    garbage_collection: Optional[bool] = None,
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        data = {
            "repeat": repeat,
            "number": number,
            "warmups": warmups,
            "garbage_collection": garbage_collection,
        }
        wrapper._config = {k: v for k, v in data.items() if v is not None}

        return wrapper

    return decorator


def skipif(condition: bool, reason: str = ""):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._skip = condition

        return wrapper

    return decorator


def parametrize(
    argnames: Union[dict[str, Any], Iterable[str]],
    argvalues: Optional[Union[Iterable]] = None,
    setup: Optional[Callable] = None,
):
    if not isinstance(argnames, dict) and argvalues is None:
        raise TypeError("")

    if isinstance(argnames, dict):
        argvalues = itertools.product(*argnames.values())
        argnames = argnames.keys()

    kwargs_list = []
    for params in argvalues:
        kwargs = {
            param_name: param
            for param_name, param in zip(argnames, params, strict=True)
        }

        kwargs_list.append(kwargs)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._params = kwargs_list
        wrapper._setup = setup

        return wrapper

    return decorator


def metadata(**metadata_kwargs):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._metadata = metadata_kwargs

        return wrapper

    return decorator
