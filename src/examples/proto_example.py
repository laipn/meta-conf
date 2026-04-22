from src.examples.example_pb2 import Person, PhoneNumber

from src.lib.decorators import Lazy, template
from src.lib.protobuf import data_template
from src.lib.var_stack import get_var, let

Person = data_template(Person)
PhoneNumber = data_template(PhoneNumber, lambda person, p: person.phones.append(p))


@template
def id(name):
  return hash(name)


@Lazy
def international_number(local_number):
  return f"+1 {local_number}"


def main():
  with let(name="Alice"):
    # Because 'name' is a field on the Person data-type, it is implicitly populated from the var_stack.
    with let(person=Person(id=id(), phones=[])):
      with let(number=international_number):
        with let(local_number="123-456-7890"):
          # 'person' is on var stack. PhoneNumber() appends itself to person.phones as a side-effect.
          PhoneNumber()
        with let(local_number="098-765-4321"):
          PhoneNumber()

      print(get_var("person"))
      # Output:
      #
      # id: 5853889631074042065
      # name: "Alice"
      # phones {
      #   number: "+1 123-456-7890"
      # }
      # phones {
      #   number: "+1 098-765-4321"
      # }


if __name__ == "__main__":
  main()
