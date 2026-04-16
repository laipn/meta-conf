from typing import Callable

from pydantic import BaseModel

from src.lib import decorators
from src.lib.var_stack import VarStack, VarStackSingleton


def data_template[T: BaseModel, V](
  model_class: type[T],
  callback: Callable[[V, T], None] | None = None,
  var_stack: VarStack = VarStackSingleton,
) -> Callable[..., T]:
  return decorators.data_template(
    data_type=model_class,
    params=model_class.model_fields.keys(),
    callback=callback,
    var_stack=var_stack,
  )
