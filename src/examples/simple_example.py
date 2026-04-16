from src.lib.decorators import Lazy, template
from src.lib.var_stack import let


@Lazy
def x_plus_y(x, y):
  return x + y


@template
def print_x(x):
  print(x)


@template
def print_z(z):
  print(z)


def main():
  with let(z=x_plus_y):
    try:
      print_z()  # Results in an error as *x* and *y* are not defined.
    except TypeError:
      pass
    with let(x=5, y=10):
      print_x()  # Output: 5. Implicit argument *x* is on var stack.
      with let(x=15):
        print_x()  # Output: 15. x=15 is on top of the var stack.
      print_x(x=6)  # Output: 6. *x* passed explicitly has priority over *x* on stack.
      print_z()  # Output: 15. lazy_x_plus_y is lazy evaluated when *z* is popped off the stack.

    with let(x=20, y=25):
      print_z()  # Output: 45. New values for *x* and *y* are on the stack.


if __name__ == "__main__":
  main()
