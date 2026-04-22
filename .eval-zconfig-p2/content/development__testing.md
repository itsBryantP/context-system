# Testing

All our tests use [pytest](https://docs.pytest.org/en/stable/) with some tests running both on/off platform and others limited to only running on z/OS. Tests can be found in the `zconfig/tests/` directory and are generally split between units, integration and functional.

The easiest way to tell what runs where is if a test function has the pytest skip marker like the following. If a test has one of these annotations it is only ever run on z/OS. All unit tests should be able to run both on z/OS and off platform.

```py
@pytest.mark.skipif(system() != "OS/390", reason="Test can only run on z/OS")
```

### Running unit test locally

You should be able to run the unit tests locally off platform (not on z/OS) by using `poetry run pytest` in your terminal. There are also some run configurations provided to allow you to execute these tests within your vs code environment as well. Simply go to the `Run and Debug` tab, and then use the drop down box at the top of the tab to select the configuration to run. There is also one to run the coverage tool and automatically open a coverage report showing in the code base where the unit tests have not covered specific code paths. We do not mandate a coverage level but it is a useful tool for writing unit tests.

### Running tests on z/OS using [GRUB](https://github.com/andrewhughes101/grub)

If you use the dev container configuration, you will also get an install of the GRUB client tool. This is currently using Drew's fork of Mike Fulton's original GRUB tool, with some enhancements to allow it to not pre-requisite any z/OS based setup/install.

The tool allows you to run a build task directly from your VS Code environment (using Cmd + Shift + B) which will push the code base to an SSH host (defined in your SSH config file) using Git, hence the name Git Remote User Build (GRUB). The build task is configured in the `tasks.json` file under the `.vscode` directory, and the content GRUB runs on the remote is the `build` file in the top level of the repository. This is also used in our CI/CD pipeline to handle connections to z/OS. In future, as our requirements become more complex, this may need to be re-evaluated in favour of something like Ansible, but for now this provides a nice lightweight experience to support remote development of a z/OS Python application.

To configure, GRUB a few settings are needed. These are the following:

```json
{
	"grub.server_root": "/u/hughea/dev", // Location on z/OS UNIX where the repo will be cloned to
	"grub.server": "hughea_mvs28", // Name of the host in your ssh config file you wis to use
	"grub.client_build_tool": "/Users/andrewhughes/grub/bin/grub_client", // Location on local device of where the grub_client is. This is defaulted in the devcontainer config
	"grub.server_git_dir": "/u/hughea/zopen/usr/local/bin" // Location on z/OS UNIX where a git client is installed. This is defaulted (to the Hursley Plex2 install) in the devcontainer config
}
```

### Functional tests

The functional tests rely on a pytest fixture called `setup_env` under the functional tests framework module (`zconfig/tests/functional/framework.py`). This fixture is responsible for building the python project into a wheel, and creating a new virtual environment with the product and its dependencies. This allows us to then write `pytest` style tests that exercise the product using subprocess calls and running the tool with YAML file inputs. Currently there is a single configurable `run_tool` method used to execute the `zconfig` CLI with some provided arguments. Like other parts of the codebase it is very CICS Region oriented and would take some time to adapt to being more generic, although it would be possible!
