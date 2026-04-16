from typing import Callable

from google.protobuf.message import Message

from src.lib import decorators
from src.lib.var_stack import VarStack, VarStackSingleton


def data_template[T: Message, V](
  message_class: type[T],
  callback: Callable[[V, T], None] | None = None,
  var_stack: VarStack = VarStackSingleton,
) -> Callable[..., T]:
  return decorators.data_template(
    data_type=message_class,
    params=[field.name for field in message_class.DESCRIPTOR.fields],
    callback=callback,
    var_stack=var_stack,
  )
