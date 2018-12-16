# ecs consul reg

Docker container registration for Consul on AWS ECS.

You may want to use [registrator](https://github.com/gliderlabs/registrator) instead.
Main differences:

- python based (If I was comfortable with Golang I would probably just contribute to registrator instead)
- intended to be run on ec2 not within docker
- keeps detailed logs (json file)
- Uses Docker Health instead of running it's own checks
    - @see [gliderlabs:issues/578](https://github.com/gliderlabs/registrator/issues/578)

## Install on Amazon ECS-Optimized Amazon Linux AMI 2

Pip is not installed:

    curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
    python get-pip.py

## Install

    pip install ecs-consul-reg

## Run

    ecs-consul-reg
 
## Initctl script

    todo~

## Options

    CONSUL_HOST=127.0.0.1
    CONSUL_PORT=8500

Options can be supplied as env or in yaml config.

```
Usage: main.py [OPTIONS]

Options:
  -c, --config TEXT
  -lf, --logfile TEXT
  -ll, --loglevel TEXT
  --help                Show this message and exit.
```





