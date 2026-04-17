# Code Templates: An idiomatic solution to Meta-Configuration

There's a common pattern in software deployment where you have a configuration file (Docker Compose files, Kubernetes manifests, Traefik, etc.) that describes how to set up and configure an application.

[Helm Charts](https://helm.sh/docs/chart_template_guide/values_files) ([example](https://github.com/docker/awesome-compose/blob/master/elasticsearch-logstash-kibana/compose.yaml)), [Env Files](https://man7.org/linux/man-pages/man1/envsubst.1.html) ([example](https://www.baeldung.com/linux/envsubst-command)) and [Jinja](https://github.com/pallets/jinja) are example solutions to this problem.

In any production setup of non-trivial complexity, people inevitably decide to code a way to generate that configuration.

This doc suggests an idiomatic solution to the "config generation" problem.

## Theory

In order to demonstrate the value of this approach, it is important to define exactly what are the constraints underlying the problem of meta-configuration.  We propose that the "meta-configuration problem" involves:

[Humans](#humans) creating [readable code](#code) to instantiate [Data Types](#data-types)

Where:

1. Humans: Refer to users like SREs who want to define application configuration.  Importantly, this means information does *not* come from external services, rather they are "sources of truth" defined by humans. e.g. the name of the AWS region we use for a Kubernetes manifest is decided by humans, not a third party service. <a name="humans"></a>
2. Readable Code: The term "code" here is loose. It is just what instantiates the data-type in question. It includes using external tools "envsubst" with an env file. Readability is important because it means users can modify it for different use-cases.  For example being able to instantiate the mostly-the-same kubernetes deployment for both production and test environment. <a name="code"></a>
3. Data Types: Examples: YAML, JSON, Protobufs etc.  Configs always have some well-defined structure to them, specifically they are always a form of [Algebraic Data Type](https://en.wikipedia.org/wiki/Algebraic_data_type). <a name="data-types"></a>

## Background

### Standard Approaches

Since the goal of writing this code is for it to be "readable", an approach ought to be as simple and [idiomatic](https://en.wikipedia.org/wiki/Programming_idiom) as possible. Given the desired data-structure to instantiate there should only be one obvious way to "code" a solution for it.

Because the source-of-truths comes from humans, it often makes sense to separate core "truths" (or axioms) from the rest of "code".  Consider this env-subst [example](https://oneuptime.com/blog/post/2026-03-06-use-flux-envsubst-variable-substitution/view):

```bash
# Set environment variables

export APP_NAME="my-web-app"
export APP_IMAGE="nginx"
export APP_TAG="1.25"
export APP_REPLICAS="3"
```

```bash
# Create a template with variable placeholders
cat <<'YAML' | flux envsubst
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  namespace: default
spec:
  replicas: ${APP_REPLICAS}
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
    spec:
      containers:
        - name: ${APP_NAME}
          image: ${APP_IMAGE}:${APP_TAG}
          ports:
            - containerPort: 80
YAML
```

The env-vars (e.g. `${APP_NAME}`) are truths (axioms) decided by a human and can easily be changed by a human. The YAML is templated with *${VAR_NAME}* statements and combined with env-vars generates the desired configuration.

This works well for simple configs, but is often too simplistic for real-world scenarios.  For [example](https://blog.searce.com/transform-kubernetes-manifests-into-helm-chart-f3d100688423), Helm templates add more complex mechanisms:

```yaml
# values.yaml
labels:
    app: web
    env: dev
    managed-by: Helm
    version: v1
selector_labels:
    app: web
    env: dev
```

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-deploy
  namespace: {{ .Values.namespace }}
  labels:
    {{- range $key,$value := .Values.labels }}
    {{ $key }}: {{ $value }}
    {{- end }}
spec:
  selector:
    matchLabels:
      {{- range $key,$value := .Values.selector_labels }}
      {{ $key }}: {{ $value }}
      {{- end }}
  {{- if .Values.replica_count }}
  replicas: {{ .Values.replica_count }}
  {{- end }}
  template:
    metadata:
      labels:
        {{- range $key,$value := .Values.selector_labels }}
        {{ $key }}: {{ $value }}
        {{- end }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: {{ .Values.image }}
        ports:
          - containerPort : {{ .Values.containerPort }}
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
```

Similar to env-vars in previous example, values.yaml is the source of truth for the template deployment.yaml file. However note the various programming constructs now used in the template: if statements, for-loops, etc.  The "template" now resembles yet-another-programming-language adding to requisite cognitive load.

The other end of the spectrum is to generate configuration entirely inside a programming language.  For [example](https://github.com/cdk8s-team/cdk8s-examples/blob/main/python/cdk8s-core/main.py):

```python
#!/usr/bin/env python
from cdk8s import App, Chart
from constructs import Construct
from imports import k8s


class MyChart(Chart):
  def __init__(self, scope: Construct, ns: str, app_label: str):
    super().__init__(scope, ns)

    # Define a Kubernetes Deployment
    k8s.KubeDeployment(
      self,
      "my-deployment",
      spec=k8s.DeploymentSpec(
        replicas=3,
        selector=k8s.LabelSelector(match_labels={"app": app_label}),
        template=k8s.PodTemplateSpec(
          metadata=k8s.ObjectMeta(labels={"app": app_label}),
          spec=k8s.PodSpec(
            containers=[
              k8s.Container(
                name="app-container",
                image="nginx:1.19.10",  # Using public nginx image
                ports=[
                  k8s.ContainerPort(container_port=80)])]))))

app = App()
MyChart(app, "getting-started", app_label="my-app")

app.synth()
```

This typically leads to [Creational Design Patterns](https://en.wikipedia.org/wiki/Creational_pattern) (e.g. Factory of Factories): complicated "code" difficult to understand than. For example consider the problem of using `image="nginx:1.19.10"` vs `image="nginx:latest"` in prod vs environments. Doing so requires plumbing new parameters into `MyChart.__init__`. As would customization for changing `name="app-container"` or `replicas=3`.

Note there is benefit in that the [Data Type](#data-type) we're building is [reified](formally) in the code itself (unlike textual templates). This means that a lot of useful validation (e.g. type-checking) is performed.

What we need here is "templating" behavior but without being limited to textual replacements.  We want the simplicity of the "textual templating" (go-templates, etc) but applied to programming data-types (json dictionaries, python [dataclasses](https://docs.python.org/3/library/dataclasses.html), etc).

### What is Templating?

Contemplate the definition of "template". With textual templating, each occurrence of a variable is replaced by a user-specified parameter. Note that standard programming functions used with read-only variables accomplish the same thing.  They return their contents with variables replaced with user-supplied arguments.  So let's call this approach a **Code Templating**.

The main downside of using functions as templates in this way is that arguments must still be passed explicitly:

```python
class MyChart(Chart):
  def nginx_version(prod_env):
    if prod_env == "dev":
      return "nginx:latest"
    if prod_env == "prod"
      return "nginx:1.19.10"

  def __init__(self, scope: Construct, ns: str, app_label: str, prod_env: str):
    ...
            containers=[
              k8s.Container(
                name="app-container",
                image=nginx_version(prod_env))]
    ...
```

`prod_env` in this example must be passed explicitly in `MyChart.__init__()`.  It is this passed against in `nginx_version()`. In fact it is very common to write code that just pass "up" arguments unchanged when writing instantiation or ["creational"](https://en.wikipedia.org/wiki/Creational_pattern()) code.

Not only is this verbose, it is conceptually redundant because the conceptual value of *prod_env* remains the same ("prod" or "dev") the entire duration of ***init**()*.  It's untouched.

## Concepts

### *Code Templating* using the *Variable Stack*

The idea behind our *Code templating* approach therefore, is to persists "variables" (like *prod_env*) automatically across functions.  And to treat functions that implicitly access those variables as "templates".  Example:

```python
@template
def nginx_version(prod_env):
  if prod_env == "dev":
    return "nginx:latest"
  if prod_env == "prod"
    return "nginx:1.19.10"

@template
def replica_count(prod_env):
  if prod_env == "dev":
    return 1
  if prod_env == "prod"
    return 100

with let(prod_env="prod")
  DeploymentSpec(
    ...
    replicas=replica_count(),
    containers=[            
      Container(
        name="app-container",
        image=nginx_version())]
    ...
  )
```

Rather than requiring *variables* be explicitly passed via function calls, allow *variables* to persist across function calls. This is similar in principle to ["dynamic scoping"](https://www.geeksforgeeks.org/dsa/static-and-dynamic-scoping/).  *Variables* are stored in per-variable stacks which we call in-aggregate the "Variable Stack".  To illustrate:

```python
from src.lib.decorators import template
from src.lib.var_stack import let

@template
def print_x(x):
  print(x)

with let(x=5, y=10):
  print_x()  # Output: 5. Implicit argument *x* is on var_stack.
  print_x(10) # Output: 10.  Explicit arguments have priority over var_stack.
    with let(x=15):
      print_x()  # Output: 15. x=15 is on top of the var_stack for 'x'

```

`with let(x=5):` pushes 5 onto the variable stack for 'x' for the duration of its indented block.  This should feel natural for anyone used to working with python [context managers](https://realpython.com/python-with-statement/).

`@template` decorates a function such that any parameters not provided by the caller are implicitly pulled from the top of the *Variable Stack* (or "Var Stack" or "var_stack").

See [Code Example](src/examples/simple_example.py) for runnable demo code: `bazel run //src/examples:simple_example`

### *Lazy Evaluation*: Variables as functions of other variables

Variables shouldn't be limited to being assigned constants, we often want to define variables as being a function of other variables.  A motivating example:

```python
@template
def container(name, image):
  k8s.Container(name=name,image=image, ...)

@template
def image(image_name, prod_env):
  if prod_env == 'dev':
    return f"{image_name}:latest"
  else:
    return f"{image_name}:stable"

@template
def container_name(image_name, prod_env)
  return f"{image_name}-{prod_env}"

with let(prod_env="dev"):
  with let(image_name="nginx"):
   with let(image=image(), name=container_name()):
     container()
  with let(image_name="alpine"):
   with let(image=image(), name=container_name()):
     container()
```

In this example we want to name our k8s container based off *image_name*.  We're using *templates* to do this but the code is overly verbose with multiple `with let(image=image(), name=container_name()):` statements. It would be preferably to have the code look like this:

```python
with let(prod_env="dev"):
  with let(image=image(), name=container_name()):
    with let(image_name="nginx"):
      container()
    with let(image_name="alpine"):
     container()
```

But this won't work because *image_name* isn't on the var-stack when `image()` and `container_name()` are called. Rather than having the `image()` and `container_name()` functions being evaluated straight away, we want to be able to defer that evaluation later when it is actually used -- when it is popped off the stack as a template parameter. Enter "[Lazy Evaluation](https://en.wikipedia.org/wiki/Lazy_evaluation)":

```python
from src.lib.decorators import Lazy, template

@template
def container(name, image):
  k8s.Container(name=name,image=image, ...)

@Lazy
def image(image_name, prod_env):
  if prod_env == 'dev':
    return f"{image_name}:latest"
  else:
    return f"{image_name}:stable"

@Lazy
def container_name(image_name, prod_env)
  return f"{image_name}-{prod_env}"

with let(prod_env="dev"):
  with let(image=image, name=container_name):
    with let(image_name="nginx"):
      container()
    with let(image_name="alpine"):
      container()
```

Note that image and container_name are no longer function-called:  `let(image=image, name=container_name):` vs `let(image=image(), name=container_name()`. The actual "call" (or evaluation) happens when the `@Lazy`-wrapped functions are pulled off the *Variable Stack* inside `container()`.

### "Data-type" templates

Three important python primitives have been introduced so far:

1. `let()` statements which push *variables* onto the *Variable Stack* Example: `with let(var='foo'):`.  Used to provide values to templates. Relevant [code](src/lib/var_stack.py).
2. `@template` decorators which pull parameters from the *Variable Stack* when the wrapped function is called. Used to write functions on *variables*. Relevant [code](src/lib/decorators.py).
3. `@lazy` decorators which are `@templates` that are lazy-evaluated upon being pulled off the *Variable Stack*. Used to allow *variables* to be functions of other *variables*. Relevant [code](src/lib/decorators.py).

See [Code Example](src/examples/simple_example.py) for runnable demo code: `bazel run //src/examples:simple_example`

Recall that the end-goal of meta-configuration is to instantiate a [*data type*](#data-types). Consider:

```python
@template
def container(name, image):
  k8s.Container(name=name,image=image, ...)

with let(image=image, name=container_name):
  with let(image_name="nginx"):
    container()
  with let(image_name="alpine"):
    container()
```

In this example `k8s.Container` is the data-type we are trying to instantiate. In order to instantiate `k8s.Container` we "forward" through each argument in the `container()` template.  It would be more convenient if we could directly "template" k8s.Container:

```python
Container = template(k8s.Container)

with let(image=image, name=container_name):
  with let(image_name="nginx"):
    Container()
  with let(image_name="alpine"):
    Container()
```

This doesn't work because `@template` infer variables based on the python function signature.  `k8s.Container.__init__()` doesn't have a function signature to use, it relies on processing `*args` and `**kwargs` generically. Therefore we introduce another "convenience" primitive:

`@data_template` which are like *templates*. Except instead of using python [reflection](https://en.wikipedia.org/wiki/Reflective_programming) libraries (`inspect.signature(func).parameters`) to infer the variables to pull off the *Variable Stack*, `@data_template@` uses specific [*Data Type*](#data-types) reflection APIs to do the same thing (e.g. [`pydantic.BaseMode.model_fields`](src/lib/pydantic.py)).

Protobuf [code](src/lib/protobuf.py). Pydantic [code](src/lib/pydantic.py) and relevant OpenAPI spec [example](src/examples/BUILD.bazel).

There's one additional piece of convenience functionality that `@data_templates` provides. This is described in the next section.

### Constructing Data-Type "Piece-Meal" {piecemeal}

It is often desirable to construct [data-types](#data-types) in parts.  This is especially true for list (or repeated) fields (or [recursive data-types](https://en.wikipedia.org/wiki/Recursive_data_type) in general).  Consider wanting to instantiate [this](src/examples/example.proto) data-type:

```protobuf
message Person {
  int64 id = 1;
  string name = 2;
  repeated PhoneNumber phones = 3; 
}

message PhoneNumber {
  string number = 1;
}
```

A templated instantiation of this data-type might look like:

```python
from src.examples.example_pb2 import Person, PhoneNumber
from src.lib.protobuf import data_template
from src.lib.decorators import template

Person = data_template(Person)

def CreatePerson():
  return Person(name="Alice", id=1, phones=[
    PhoneNumber(number="123-456-7890")
    PhoneNumber(number="098-765-4321")])

```

Suppose we wanted to do some useful templating on PhoneNumber.  For example to store international number rather than the domestic number provided:

```python

def international_number(number):
  return f"+1 {number}"

def CreatePerson():
return Person(name="Alice", id=1, phones=[
  PhoneNumber(number=international_number("123-456-7890")),
  PhoneNumber(number=international_number("098-765-4321"))])
```

Note the verbosity from `international_number` here that won't scale well as more PhoneNumbers are added. It would be better if we could instantiate the Person data-type in parts using templating:

```python
from src.examples.example_pb2 import PhoneNumber

@Lazy
def international_number(number):
  return f"+1 {number}"

@template
def PhoneNumberTemplate(person, number):
  # Construct phone number and then appends the result to person.phones.
  person.phones.append(PhoneNumber(number=number))

def CreatePerson():
    with let(person=Person(id=1, phones=[])):
      with let(number=international_number):
        with let(local_number="123-456-7890"):
          PhoneNumberTemplate()
        with let(local_number="098-765-4321"):
          PhoneNumberTemplate()
```

In the above, we push the *Person* we are trying to create on the stack itself (`let(person=Person...)`) so that later calls to `PhoneNumberTemplate()` will also append `Person()` to `person.phones`.

As mentioned previously `@data_template` will handle constructing `PhoneNumber` by pulling argument from the *Var Stack*.  It also offers a callback to conveniently accomplish the above.

```python
from src.examples.example_pb2 import PhoneNumber

PhoneNumber = data_template(PhoneNumber, lambda person, p: person.phones.append(p))

def CreatePerson():
    with let(person=Person(id=1, phones=[])):
      with let(number=international_number):
        with let(local_number="123-456-7890"):
          PhoneNumber()
        with let(local_number="098-765-4321"):
          PhoneNumber()
```

See [Code Example](proto_example.py) for runnable demo code: `bazel run //src/examples:proto_example`.
See [Kubernetes Pod Code Example](kubernetes_example.py) for another runnable demo code: `bazel run //src/examples:kubernetes_example`.

## Discussion: Comparative analysis

Recall that the purpose of all this templating is for meta-configuration:

> [Humans](#humans) creating [readable code](#code) to instantiate [Data Types](#data-types)

Let's compare three standard approaches to solving the problem of meta-configuration listed above:

1. Textual templates (e.g. helm templates)
2. Programming libraries (pure coding approach)
3. Code templates (the approach endorsed in this doc)

### Textual Templates {labels}

```yaml
# values.yaml
labels:
    app: web
    env: dev
    version: v1
```

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    {{- range $key,$value := .Values.labels }}
```

> **Humans** creating readable code to instantiate Data Types

Textual template typically separate "human"-sourced knowledge from the "code" (or template) that uses that knowledge.  This separates axiomatic data provided by humans from inferences from that data (e.g. the data-type we are trying to instantiate). Instantiating new data-types can be instantiated by passing in different human-provided values.

> Humans creating readable code to instantiate **Data Types**

Pure textual templating is often insufficient to allow a clean separation between "human"-sourced knowledge and the templates that consume that knowledge. The "data-types" in this case are purely represented as text which is inflexible. Consider the fact that in the above example a "labels" dictionary must be provided by the user.  But "labels" is purely a kubernetes manifest concept.  The human but therefore understand kubernetes manifest internals to understand what to provide. This is poor "[separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns)".

### Programming libraries

Consider:

```python
#!/usr/bin/env python
from cdk8s import App, Chart
from constructs import Construct
from imports import k8s

class MyChart(Chart):
  def __init__(self, scope: Construct, ns: str, app_label: str):
    super().__init__(scope, ns)

    # Define a Kubernetes Deployment
    k8s.KubeDeployment(
      self,
      "my-deployment",
      spec=k8s.DeploymentSpec(
        replicas=3,
        selector=k8s.LabelSelector(match_labels={"app": app_label}),
        template=k8s.PodTemplateSpec(
          metadata=k8s.ObjectMeta(labels={"app": app_label}),
          spec=k8s.PodSpec(
            containers=[
              k8s.Container(
                name="app-container",
                image="nginx:1.19.10",  # Using public nginx image
                ports=[
                  k8s.ContainerPort(container_port=80)])]))))

app = App()
MyChart(app, "getting-started", app_label="my-app")

app.synth()
```

> **Humans** creating readable code to instantiate Data Types:

With the "programming library" approach, there is no obvious clean separation between "human"-sourced knowledge and the data-type we are trying to instantiate. You often need to understand the code in order to understand how changing parameters will affect the data-type being created.

> Humans creating readable code to instantiate **Data Types**:

The code to do the data-type instantiation is often some form of [dataclass](https://docs.python.org/3/library/dataclasses.html) and by virtue of using python typing we have more safety guarantees than textual templates.  It is just a matter of writing code to invoke the programming libraries in the right way.

Clever programmers **can** rig the the code to more cleanly separate human-values from (for example by having MyChart.**init**() accept the right "human"-sourced arguments), but there is no apparent idiom on how to do it.  Should we use a MyChartFactory() here?  Do you use dependency inversion?

### Code templating

Consider:

```python
from src.lib.decorators import Lazy, data_template, template

Pod = data_template(IoK8sApiCoreV1Pod)
Container = data_template(
  IoK8sApiCoreV1Container, lambda pod, c: pod.spec.containers.append(c)
)

@Lazy
def image(image_name, prod_env):
  if prod_env == 'dev':
    return f"{image_name}:latest"
  else:
    return f"{image_name}:stable"

@Lazy
def container_name(image_name, prod_env)
  return f"{image_name}-{prod_env}"

with let(prod_env="dev"):
  with let(
    pod=Pod(
      api_version="v1",
      kind="Pod",
      metadata=IoK8sApimachineryPkgApisMetaV1ObjectMeta(
        name=Lazy(lambda prod_env: "Webapp." + prod_env),
      ),
      spec=IoK8sApiCoreV1PodSpec(containers=[]),
    )
  ):
    with let(image=image, name=container_name):
      with let(image_name="nginx"):
        Container()
      with let(image_name="alpine"):
        Container()
```

> **Humans** creating readable code to instantiate Data Types:

Code-templates don't separate out human-provided values in a separate file like with textual templates.  Rather human-provided values are typically passed via *Var Stack* with `with let():` statements. This is more complicated than the "separate values file" text-template, however is less complicated (more idiomatic) than the "free-form" *programming library* approach.  It is limited to using a stack for passing human-provided information. To understand what is currently "on the stack" ones reads the most recent `with let():` statement at each indentation level.

> Humans creating readable code to instantiate **Data Types**:

Instantiating data-types also has its own approach where data-structures are instantiated incrementally via `@data_template`. This avoids requiring data-structures to represent human-provided data. Instead of passing say a list of containers `image_names` we just push different values using  `with let(image_name=...):`.  Contrast that to how we were forced to represent [labels](#labels) in the textual-template section.

Incrementally building the data-structure also makes it obvious the relationship human-provided-data has with the data-type being created.  `image_name` in this example is related to creating the `k8s.Container` part of `k8s.PodSpec` whereas *prod_env* is related to building the entire

As such the "code-template" approach is a specialization of the "free-from" *programming library* approach.  It provides an idiom how to separate "human-values" (*Var Stack* *variables*) from the *templates* that rely on them; and provides idioms on how to instantiate the data-types (`@data_templates`) incrementally.
