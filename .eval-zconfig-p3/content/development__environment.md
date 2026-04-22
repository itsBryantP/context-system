
# Setting up a Development environment

## Overview

We use VS Code for development and the config tool is written in Python and uses [Poetry](https://python-poetry.org/) for dependency management.

We use Python 3.11 for development as this is the lowest supported version on z/OS. You can write and develop the code locally on your machine but some imports from the `zoautil_py` may not resolve on your local machine. This means it's important to test any code you write off-platform on z/OS before raising a pull request.

For Poetry our config uses Poetry version 2.x, however it is made to work with both Poetry version 1.X and version 2.X due to limitations imposed by the Mend dependency scanner.

As we're using Python for development, try to follow [standard Python conventions for naming](https://llego.dev/posts/python-naming-conventions-and-best-practices-for-class-and-object-names/).

It is also possible to install the ZOAU python wheels directly on your local machine off-platform. This will mean the dependencies resolve in your local Python editor, however the code paths won't be able to be fully executed as the shared library calls from the ZOAU API won't work off z/OS.

## Devcontainer

We have a dev container configuration setup in this repository to automatically create you a development environment and define our tool-chain versions in code. If you are not familiar, try following the [VSCode documentation](https://code.visualstudio.com/docs/devcontainers/containers) to get going. If you get stuck, reach out to anyone in the team as we are all quite familiar with these already.

## Getting started
If not using the dev container configuration, download and install the following:
- Python 3.11 (If using Mac, try using [pyenv](https://github.com/pyenv/pyenv) to manage your Python install)
- [Poetry](https://python-poetry.org/)

Once installed open the project in VS Code and ensure you have the following extensions installed to benefit from the configuration in the [.vscode/settings.json](https://github.ibm.com/etsi/z-dec-spec/blob/main/.vscode/settings.json):
- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [isort](https://marketplace.visualstudio.com/items?itemName=ms-python.isort)
- [autopep8](https://marketplace.visualstudio.com/items?itemName=ms-python.autopep8)
- [yaml](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)

Use `poetry install --with=local-dev` to install all the local dependencies into a Poetry-managed virtual environment, including development and testing dependencies such as `pytest` and `detect-secrets`.

## Developing on z/OS

It is possible to develop the tool directly on z/OS, although the experience is somewhat lacking. this is why we've gone to such lengths as to provide a good development experience off-platform but still incorporate z/OS for the testing loop. If you do decide to develop directly on z/OS its good to be aware of a few caveats:

- The latest version of Poetry may not install on z/OS. This is due to transitive dependencies now pre-reqing a newer version of cffi that is not included in the Python z/OS install. To get around this, install any version of poetry < 2.1.0.
- Do not try to install all development dependencies. The `local-dev` group was created to specifically house dependencies that may not be able to be installed on z/OS. Therefore use a simple `poetry install` command to install dependencies.


## Manually testing changes on z/OS

To run the tool on z/OS, ensure you have a copy of IBM Open Enterprise SDK for Python installed at a version of at least 3.11, along with an installation of IBM Z Open Automation Utilities at a version of at least 1.3.


To build the Python wheel locally, use the command:

```sh
poetry build
```

This will create a new wheel under the `dist` directory. Copy this wheel to z/OS using a command like:

```sh
scp ./dist/cicsconfig-0.1.3.dev1-py3-none-any.whl HUGHEA@winmvs28.hursley.ibm.com:/u/hughea
```

On z/OS simply `pip install` the wheel file. This will add the package to your user's Python site-packages under a directory such as `$HOME/.local`. Alternatively, set up a virtual environment to install the wheel into to provide an isolated install of the product that's easier to manage. 

Once pip-installed, there should be a new script called `cicsconfig` under the `bin` directory of where your python packages are installed, so for example `.venv/bin` for a virtual environment called `.venv` or under `$HOME/.local/bin` if installing python packages under your own user. 

You will need to ensure you have also installed the ZOAU Python api wheel or setup the `PYTHONPATH` var (I wouldn't recommend this method over the wheel install).

To then test the tool, simply run `cicsconfig --help`. You should see some output like the following:

 ```sh
$ cicsconfig --help
usage: cicsconfig -d DIRECTORY [-v] [-l] [--suppress-warnings] [-h]

options:
  -d DIRECTORY, --directory DIRECTORY
                        (str, required)
  -v, --verbose         (int, default=0)
  -l, --logging         (bool, default=False)
  --suppress-warnings   (default=False)
  -h, --help            show this help message and exit
```

This will indicate you have installed the tool correctly and have correctly configured the ZOAU Python API.
