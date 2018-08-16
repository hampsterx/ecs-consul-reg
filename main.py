import sys
import traceback
import logging
import json
import yaml
import consul
import click

from docker.models.containers import Container
import docker


# Monkey Patch
# @see https://github.com/docker/docker-py/pull/1726

@property
def health(self):
    """
    The health of the app in the container.
    """
    if self.attrs['State'].get('Health') is not None:
        return self.attrs['State']['Health']['Status']
    else:
        return 'none'

Container.health = health


log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler())
log.setLevel(logging.DEBUG)






#check =

# http://172.31.141.175:8500/v1/catalog/service/test

#c.agent.service.deregister(service_id="test")


#raise

"""


while True:
    import time
    time.sleep(1)

    for c in client.containers.list():
        print(c.id, c.status, c.health)

raise

events = client.events()

log.info("Starting up..")

for event in events:
    #import pdb
    #pdb.set_trace()

    

    print(action, type)

    if type != 'container':
        continue

    print(action)

    #if action not in ['start', 'die', 'kill', 'oom']:
    #    continue

    status = data['status']
    id = data['id']

    print(json.dumps(data, indent=True))

"""




class ECSConsulReg:

    def __init__(self, config):
        self.config = config
        self.docker_client = docker.from_env()
        self.docker_api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

        self.consul_client = consul.Consul(host=config['ConsulHost'], port=int(config.get('ConsulPort', 8500)))
        self.registered = {}

    def watch_events(self):
        events = self.docker_client.events()
        for event in events:
            data = json.loads(event.decode("utf-8"))

            action = data['Action']
            type = data['Type']

            # Ignore health checks
            if "exec_" in action:
                continue

            # Ignore image destroy (ecs does this regularly)
            if action == 'destroy':
                continue

            log.debug("Event [{}] type=[{}]".format(action, type))

            if type != 'container':
                continue

            if action not in ['health_status: healthy', 'health_status: unhealthy', 'pull', 'start', 'stop', 'die', 'kill', 'oom']:
                continue

            id = data['Actor']['ID']
            name = data['Actor']['Attributes'].get('com.amazonaws.ecs.container-name', None)

            if not name:
                continue

            log.info("{} - {}".format(name, action))

            if action == "health_status: unhealthy":
                if id in self.registered:
                    self.deregister_service(id, name)
                continue

            if action == "health_status: healthy":
                port = self.get_host_port(id)
                if not port:
                    log.info("Skipping {} as no port found".format(name))
                    continue
                self.register_service(id, name, port)
                continue

            if action in ['kill', 'die', 'stop']:
                if id in self.registered:
                    self.deregister_service(id, name)
                continue


    def get_host_port(self, container_id):
        port_data = self.docker_api_client.inspect_container(container_id)['NetworkSettings']['Ports']

        if port_data:
            host_info = port_data[port_data.keys()[0]][0]
            return int(host_info['HostPort'])

        return None

    def deregister_service(self, id, name):
        log.info("Deregestering {} ({})".format(id, name))
        self.consul_client.agent.service.deregister(service_id=id)
        self.registered.pop(id)

    def deregister_services(self):
        for id, name in self.registered.items():
            self.deregister_service(id, name)

    def register_service(self, id, name, port):
        log.info("Registering {} ({})".format(name, port))
        self.registered[id] = name

        self.consul_client.agent.service.register(name=name, service_id=id, port=port, tags=['app']) #, check=check)

    def register_healthy_containers(self):
        containers = [c for c in self.docker_client.containers.list()]

        for c in containers:
            if c.health != 'healthy':
                log.info("Skipping {} as not healthy".format(c.id))
                continue

            port = self.get_host_port(c.id)
            if not port:
                log.info("Skipping {} as no port found".format(c.id))
                continue

            name = c.labels['com.amazonaws.ecs.container-name']

            self.register_service(id=c.id, name=name, port=port)

    def get_services(self):
        return self.consul_client.agent.services()



@click.command()
@click.option('--config', default="/etc/ecs-consul-reg.yaml")
def main(config):


    with file(config, 'r') as f:
        config = yaml.load(f)

    try:
        reg = ECSConsulReg(config)
        reg.register_healthy_containers()
        reg.watch_events()

    except KeyboardInterrupt:
        log.info("Keyboard Interupt... exiting")
    except SystemExit:
        log.info("System Exit... exiting")
    except Exception:
        log.error(traceback.format_exc())
    finally:
        reg.deregister_services()


if __name__ == "__main__":
    main()