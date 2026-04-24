import inspect
from collections.abc import Iterable
from functools import wraps
from typing import Any, Callable

from src.lib.var_stack import (
  LazyEvaluatedValue,
  VarStack,
  VarStackSingleton,
  pull_params_from_stack,
)

Lazy = LazyEvaluatedValue


def template[**P, R](
  func: Callable[P, R],
  var_stack: VarStack = VarStackSingleton,
) -> Callable[..., R]:
  """Implicitly pulls parameters for *func* from *var_stack*."""

  return pull_params_from_stack(func, None, var_stack)


def data_template[T, V](
  data_type: type[T],
  on_creation: Callable[[V, T], None] | None,
  params: Iterable[str],
  var_stack: VarStack,
) -> Callable[..., T]:
  """Implicitly pull *params* for constructing T from var_stack. Invokes
  *callback* on T() with the first argument pulled from *var_stack*."""

  # From https://stackoverflow.com/questions/6394511/python-functools-wraps-equivalent-for-classes
  @wraps(data_type, updated=())
  def wrapper(*args: Any, **kwargs: Any) -> T:
    instance = data_type(*args, **kwargs)
    if on_creation:
      first_param_name = list(inspect.signature(on_creation).parameters.keys())[0]
      first_param = var_stack.peek(first_param_name)
      on_creation(first_param, instance)
    return instance

  return pull_params_from_stack(wrapper, params, var_stack)
