Understanding plugins structure
===============================
Plugins are the base for all Orcha systems. Without plugins, Orcha
does nothing.

Orcha expects plugins to have an specific structure in order to detect
them and use them. There are two kind of plugins:

+ Command line plugins (the usual).
+ Library plugins (not plugins at all).

The concept of plugin stands for a software addon which enhances the
capabilities of Orcha, so the common one will be the CLI plugins (as a
Python application inheriting and defining its own behavior based on
:mod:`orcha.lib` is considered a new application rather than a plugin).

You can also define a plugin that may be used by other plugins, but this
is not documented right now.

Naming conventions
------------------
All Orcha plugins must follow a name convention in order to be found
and detected. They must be called ``orcha_<PLUGIN_NAME>`` (i.e.:
``orcha_jenkins``, ``orcha_builder``, etc). If the plugin name does
not start with ``orcha_`` then it won't be found when looking for plugins.

For this example, we will be creating a plugin that will print a hello
world text with an incrementing counter, so the plugin will be called
``orcha_hw``.

Packaging conventions
---------------------
All plugins must inherit from :class:`orcha.plugins.BasePlugin` and export
an alias to that class at package level. This means that our plugin class
must be accessible by simply typing::

    orcha_plugin.plugin

in which ``plugin`` is the alias to our class. This is not a whim but a
requirement in order to correctly load your plugins into Orcha.

.. note::
    When loading plugin's class, checks are made in order to assert
    that the value is a subclass of :class:`BasePlugin <orcha.plugins.BasePlugin>`
    and that the plugin has an exported member whose name is "plugin".

The base plugin class
---------------------
:class:`orcha.plugins.BasePlugin` is the heart of the plugins system. It
allows you to develop your own fully capable plugins that interact with
the orchestrator.

:class:`BasePlugin <orcha.plugins.BasePlugin>` exposes three attributes
that are used for defining your command:

+ ``name`` is the command name on CLI (in this example, ``hello-world``).
+ ``aliases`` is a :obj:`tuple` which contains possible alias for your command (i.e.: ``hw``).
+ ``help`` is an arbitrary string containing the text displayed when issuing ``--help``.

In such class you must override some methods and attributes in order
to fully work. When a command that your plugin is able to run is entered,
the :func:`handle() <orcha.plugins.BasePlugin.handle>` will be called and
you will have the control over the program execution.

.. note::
    This is intended to be a brief introduction into the plugins system.
    For more information, please refer to :mod:`orcha.plugins` documentation
    which has more details about how it works the plugin system and more.
