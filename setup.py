from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='ecs-consul-reg',
      description='AWS ECS Consul Registration',
      long_description=long_description,
      long_description_content_type="text/markdown",
      version='0.0.7',
      url='https://github.com/hampsterx/ecs-consul-reg',
      author='Tim van der Hulst',
      author_email='tim.vdh@gmail.com',
      license='Apache2',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2'
      ],
      packages=['ecs_consul_reg'],
      install_requires=[
          'PyYAML',
          'python-consul==1.1.0',
          'docker==3.5.0',
          'click==6.7'
      ],
      entry_points={
          'console_scripts': [
              'ecs-consul-reg=ecs_consul_reg.main:main'
          ]
      }
)