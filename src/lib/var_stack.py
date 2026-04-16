import inspect
from collections.abc import Iterable
from contextlib import contextmanager
from functools import wraps
from itertools import islice
from pathlib import Path
from typing import Any, Callable, cast


class VarStack:
  var_dict: dict[str, list[Any]]

  def __init__(self):
    self.var_dict: dict[str, list[Any]] = {}

  def __contains__(self, var_name: str) -> bool:
    return var_name in self.var_dict

  def __repr__(self):
    return repr(self.var_dict)

  def peek(self, var_name: str) -> Any:
    if var_name not in self.var_dict:
      raise IndexError(f"VarStack for '{var_name}' is empty")
    return_val = self.var_dict[var_name][-1]
    if isinstance(return_val, LazyEvaluatedValue):
      return_val = return_val.evaluate(self)
    return return_val

  def pop(self, var_name: str) -> None:
    if var_name not in self.var_dict:
      raise IndexError(f"VarStack for '{var_name}' is empty")
    val = self.var_dict[var_name].pop()
    if len(self.var_dict[var_name]) == 0:
      del self.var_dict[var_name]
    return val

  def push(self, var_name: str, var_value: Any) -> None:
    if var_name not in self.var_dict:
      self.var_dict[var_name] = []
    self.var_dict[var_name].append(var_value)


VarStackSingleton = VarStack()


def get_var(var_name: str, var_stack: VarStack = VarStackSingleton) -> Any:
  return var_stack.peek(var_name)


@contextmanager
def let(var_stack: VarStack = VarStackSingleton, **kwargs: Any):
  try:
    for var_name, var_value in kwargs.items():
      var_stack.push(var_name, var_value)
    yield None
  finally:
    for var_name, var_value in kwargs.items():
      var_stack.pop(var_name)


def pull_params_from_stack[**P, R](
  func: Callable[P, R],
  params: Iterable[str] | None,
  var_stack: VarStack,
) -> Callable[..., R]:
  """Decorate that add arguments in *params* (pulling from *var_stack*) to kwargs."""

  if params is None:
    params = inspect.signature(func).parameters.keys()

  @wraps(func)
  def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
    # Positional args take up the first n params. Remove them.
    positional_args_removed = islice(params, len(args), None)
    params_not_present_in_kwargs = [
      param for param in positional_args_removed if param not in kwargs.keys()
    ]
    # If params is neither positional nor in kwargs, pull it from var_stack
    for param in params_not_present_in_kwargs:
      if param in var_stack:
        kwargs[param] = var_stack.peek(param)

    return cast(Callable[..., R], func)(*args, **kwargs)

  return wrapper


class LazyEvaluatedValue[**P, R]:
  """Wraps a function and evaluates it lazily pulling args from *var_stack*."""

  def __init__(self, func: Callable[P, R]):
    self.func = func

  def evaluate(self, var_stack: VarStack) -> R:
    return pull_params_from_stack(self.func, None, var_stack)()

  def __repr__(self) -> str:
    func_name = self.func.__name__
    line = inspect.getsourcelines(self.func)[1]
    signature = inspect.signature(self.func)
    source_file = Path(inspect.getfile(self.func)).name
    return f"'{func_name}{signature} at {source_file}:{line}'"
