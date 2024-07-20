import pybench


@pybench.config(number=10)
@pybench.parametrize({"a": [1, 2], "b": [3, 4]})
def bench_my_func(a, b):
    return a * b


@pybench.config(number=10)
@pybench.parametrize({"a": [1, 2], "b": [3, 4]})
def bench_my_func2(a, b):
    return a + b
