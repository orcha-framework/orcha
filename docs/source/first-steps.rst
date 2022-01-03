Installing Orcha
================
Orcha is currently available from the following sources:

+ `PyPi <https://pypi.org/project/orcha/>`_ (*not regularly updated*).
+ `Jenkins <http://jenkins.id.teldat.com/job/orcha/>`_ (*updated on every commit*).

The PyPi package is updated manually when required, as it may be used by
other projects as a dependency but it is not intended to have the latest
package version on every commit or update (as 3rd of January, 2022).

Instead, using the Debian package provided by Jenkins is preferred: on
every commit, the package is built and is ready to be installed on the
host machine.

Installing the package is as simple as running::

    sudo apt install -f ./orcha_<version>.deb

That will ask you to install also the required dependencies and everything
else. You can check if Orcha was correctly installed by issuing::

    orcha --version
    orcha --help
    orcha ls

The output should be similar to the following::

    $ orcha --version
    orcha - 0.1.5b9
    $ orcha --help
    usage: orcha [-h] [--listen-address ADDRESS] [--port N] [--key KEY] [--version] {list-plugins,ls} ...

    Orcha command line utility for handling services

    optional arguments:
      -h, --help            show this help message and exit
      --listen-address ADDRESS
                            Listen address of the service
      --port N              Listen port of the service
      --key KEY             Authentication key used for verifying clients
      --version             show program's version number and exit

    subcommands:
      Available commands

      {list-plugins,ls}
        list-plugins (ls)   list the installed plugins on the system and exit
    $ orcha ls
    orcha - 0.1.5b9
    └ list-plugins* - 0.0.1

    Plugins marked with an asterisk (*) are embedded plugins


In addition, once installed you can also access :mod:`Orcha's library <orcha.lib>` from
Python command line, if everything went OK::

    >>> import orcha
    >>> dir(orcha)
    ['ActionCallbackT', 'B', 'BasePlugin', 'ClientManager', 'EmptyPetition', 'LOGGER_NAME', 'Manager', 'ManagerShutdownError', 'Message', 'P', 'Petition', 'ProcT', 'Processor', 'ServiceWrapper', '__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__path__', '__spec__', 'authkey', 'bin', 'exceptions', 'extras', 'get_logger', 'interfaces', 'kill_proc_tree', 'lib', 'listen_address', 'main', 'plugins', 'port', 'properties', 'query_plugins', 'register_service', 'run_command', 'start_service', 'utils', 'version']
    >>> orcha.version()  # get our own version
    0.1.5b9

