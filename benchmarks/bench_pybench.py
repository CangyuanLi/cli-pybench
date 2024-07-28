import pybench


@pybench.config(number=10)
def bench_my_func4():
    return 1


@pybench.skipif(True)
@pybench.config(number=10)
def bench_my_func5():
    return 1


@pybench.config(number=10)
@pybench.skipif(True)
def bench_my_func6():
    return 1


@pybench.config(number=10)
@pybench.parametrize({"a": [1, 2], "b": [3, 4]})
def bench_my_func(a, b):
    return a * b


@pybench.skipif(False)
@pybench.parametrize({"a": [1, 2], "b": [3, 4]})
def bench_my_func2(a, b):
    return a + b


def setup(a):
    return {"a": a + 1}


@pybench.parametrize({"a": [1, 2]}, setup=setup)
def bench_my_func3(a):
    return a


@pybench.parametrize(("a", "b"), [(1, 2), (3, 4)])
def bench_my_func8(a, b):
    return a + b
