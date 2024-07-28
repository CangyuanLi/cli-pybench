import functools
import itertools
from collections.abc import Iterable
from typing import Any, Callable, Optional, Union


def config(**config_kwargs):
    def decorator(func):
        @functools.wraps(func)
        def wrapper():
            func._config = config_kwargs

            return func

        return wrapper

    return decorator


def skipif(condition: bool, reason: str = ""):
    def decorator(func):
        @functools.wraps(func)
        def wrapper():
            func._skip = condition
            return func

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

    def decorator(func):
        @functools.wraps(func)
        def wrapper():
            funcs = []
            for params in argvalues:
                kwargs = {
                    param_name: param
                    for param_name, param in zip(argnames, params, strict=True)
                }

                if setup is None:
                    part = functools.partial(func, **kwargs)
                else:
                    part = functools.partial(func, **setup(**kwargs))

                part._params = kwargs

                funcs.append(part)

            func._funcs = funcs

            return func

        return wrapper

    return decorator
