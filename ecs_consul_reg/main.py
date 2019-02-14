import os
import traceback
import logging
import json
import yaml
import consul
import click
import docker
from simple_json_log_formatter import SimpleJsonFormatter
from consul import ConsulException
from requests.exceptions import ConnectionError
from logging.handlers import TimedRotatingFileHandler
from docker.models.containers import Container

log = logging.getLogger(__name__)

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

def configure_logging(options):

    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(options['loglevel'])

    if options['logfile']:
        file_handler = TimedRotatingFileHandler(options['logfile'],
                                               when="midnight",
                                               interval=1, backupCount=5)
        file_handler.setFormatter(SimpleJsonFormatter(json.dumps))
        log.addHandler(file_handler)


class Config:

    def __init__(self, file_path, defaults={}):

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                self.config = yaml.load(f)
        else:
            self.config = {}

        self.defaults = defaults

    def get(self, name):
        return os.getenv(name, self.config.get(name, self.defaults[name]))


class ECSConsulReg:

    def __init__(self, config):
        self.config = config

        # Hold Registered services
        self.registered = {}

    def init(self):

        self.docker_client = docker.from_env()
        self.docker_api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

        consul_host = self.config.get('CONSUL_HOST')
        consul_port = int(self.config.get('CONSUL_PORT'))

        log.info("Using Consul Agent at {}:{}".format(consul_host, consul_port))

        self.consul_client = consul.Consul(host=consul_host, port=consul_port)

        try:
            peers = self.consul_client.status.peers()
            log.info("Consul Agent has {} peers".format(len(peers)))
        except ConnectionError:
            log.error("Could not connect with Consul Agent. Exiting..")
            return False
        except ConsulException as e:
            log.error("Consul issue: {}".format(e))
            return False

        return True

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

            log.info("{} - {}".format(name, action), extra={'event': action, 'type': type, 'container.name': name, 'attributes': data['Actor']['Attributes'],  'service.name': "consul-reg"})

            if action == "health_status: unhealthy":
                if id in self.registered:
                    self.deregister_service(id, name)
                continue

            if action == "health_status: healthy":
                ports = self.get_host_ports(id)
                if not ports:
                    log.info("Skipping {} as no port found".format(name))
                    continue
                self.register_services(id, name, ports)
                continue

            if action in ['kill', 'die', 'stop']:
                if id in self.registered:
                    self.deregister_service(id, name)
                continue


    def get_host_ports(self, container_id):
        port_data = self.docker_api_client.inspect_container(container_id)['NetworkSettings']['Ports']
        if port_data:
            return [(int(k.split("/")[0]), int(p[0]['HostPort'])) for k,p in port_data.items()]

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

    def register_services(self, id, name, port_info):
        for ports in port_info:
            unique_name = "{}-{}".format(name, ports[0]) if len(ports) > 1 else name
            self.register_service(id="{}_{}".format(id, unique_name), name=unique_name, port=ports[1])

    def register_healthy_containers(self):
        containers = [c for c in self.docker_client.containers.list()]
        for c in containers:

            name = c.labels.get('com.amazonaws.ecs.container-name')

            if not name:
                continue

            if c.health != 'healthy':
                log.info("Skipping {} as not healthy".format(c.id))
                continue

            ports = self.get_host_ports(c.id)
            if not ports:
                log.info("Skipping {} as no port found".format(c.id))
                continue

            self.register_services(c.id, name, ports)

    def get_services(self):
        return self.consul_client.agent.services()



@click.command()
@click.option('-c', '--config', default="/etc/ecs-consul-reg.yaml")
@click.option('-lf', '--logfile', default=None)
@click.option('-ll', '--loglevel', default="INFO")
def main(config, **options):

    configure_logging(options)

    config_defaults = {
        'CONSUL_HOST': '127.0.0.1',
        'CONSUL_PORT': '8500'
    }

    config = Config(file_path=config, defaults=config_defaults)

    try:
        reg = ECSConsulReg(config)
        if not reg.init():
            return

        reg.register_healthy_containers()
        reg.watch_events()

    except KeyboardInterrupt:
        log.info("Keyboard Interupt... exiting gracefully")
    except SystemExit:
        log.info("System Exit... exiting gracefully")
    except Exception:
        log.error(traceback.format_exc())
    finally:
        reg.deregister_services()


if __name__ == "__main__":
    main()