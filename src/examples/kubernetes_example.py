from pprint import pprint

from openapi_client.models.io_k8s_api_core_v1_container import IoK8sApiCoreV1Container
from openapi_client.models.io_k8s_api_core_v1_container_port import (
  IoK8sApiCoreV1ContainerPort,
)
from openapi_client.models.io_k8s_api_core_v1_pod import IoK8sApiCoreV1Pod
from openapi_client.models.io_k8s_api_core_v1_pod_spec import IoK8sApiCoreV1PodSpec
from openapi_client.models.io_k8s_api_core_v1_volume_mount import (
  IoK8sApiCoreV1VolumeMount,
)
from openapi_client.models.io_k8s_apimachinery_pkg_apis_meta_v1_object_meta import (
  IoK8sApimachineryPkgApisMetaV1ObjectMeta,
)

from src.lib.decorators import Lazy, template
from src.lib.pydantic import data_template
from src.lib.var_stack import get_var, let

Container = data_template(
  IoK8sApiCoreV1Container, lambda pod, c: pod.spec.containers.append(c)
)
Pod = data_template(IoK8sApiCoreV1Pod)
Meta = data_template(IoK8sApimachineryPkgApisMetaV1ObjectMeta)


# In practice these would be in a separate module as config updated by humans.
CANDIDATE_RELEASES = {
  "nginx": "4.15.0",
  "alpine": "3.18.0",
}
STABLE_RELEASES = {
  "nginx": "4.12.0",
  "alpine": "3.10.0",
}


@Lazy
def image_from_prod_env(image_name: str, prod_env: str):
  if prod_env == "canary":
    return f"{image_name}:{CANDIDATE_RELEASES[image_name]}"
  if prod_env == "prod":
    return f"{image_name}:{STABLE_RELEASES[image_name]}"
  if prod_env == "dev":
    return f"{image_name}:latest"
  assert False


@template
def containers_template(image_name: str):
  LogVolume = IoK8sApiCoreV1VolumeMount(name="app-log", mountPath="/var/log/app.log")

  with let(image=image_from_prod_env):
    Container(
      name=image_name,
      ports=[IoK8sApiCoreV1ContainerPort(containerPort=80)],
      volume_mounts=[LogVolume],
    )

    with let(image_name="alpine"):
      Container(
        args=["/bin/sh", "-c", "tail -n+1 -f /var/log/app.log"],
        name=f"{image_name}-logsaver",
        volume_mounts=[LogVolume],
      )


@template
def pod_template(image_name: str, prod_env: str) -> IoK8sApiCoreV1Pod:
  with let(
    pod=Pod(
      api_version="v1",
      kind="Pod",
      metadata=IoK8sApimachineryPkgApisMetaV1ObjectMeta(
        name=f"{image_name}-{prod_env}",
        labels={"app": image_name},
      ),
      spec=IoK8sApiCoreV1PodSpec(containers=[]),
    )
  ):
    containers_template()

    return get_var("pod")


def dev_pod() -> IoK8sApiCoreV1Pod:
  with let(prod_env="dev", image_name="nginx"):
    return pod_template()


def canary_pod() -> IoK8sApiCoreV1Pod:
  with let(prod_env="canary", image_name="nginx"):
    return pod_template()


def main():
  pprint(canary_pod().model_dump(exclude_unset=True))
  # Output:
  # {'api_version': 'v1',
  #  'kind': 'Pod',
  #  'metadata': {'labels': {'app': 'nginx'}, 'name': 'nginx-canary'},
  #  'spec': {'containers': [{'image': 'nginx:4.15.0',
  #                           'name': 'nginx',
  #                           'ports': [{'container_port': 80}],
  #                           'volume_mounts': [{'mount_path': '/var/log/app.log',
  #                                              'name': 'app-log'}]},
  #                          {'args': ['/bin/sh',
  #                                    '-c',
  #                                    'tail -n+1 -f /var/log/app.log'],
  #                           'image': 'alpine:3.18.0',
  #                           'name': 'nginx-logsaver',
  #                           'volume_mounts': [{'mount_path': '/var/log/app.log',
  #                                              'name': 'app-log'}]}]}}


if __name__ == "__main__":
  main()
