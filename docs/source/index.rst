.. Orcha documentation master file, created by
   sphinx-quickstart on Mon Dec 20 10:52:26 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Orcha's documentation!
=================================
Here you will find useful documentation in which where to start, work
and develop is shown. This main page conforms an start point to every
user when developing a new plugin with Orcha or trying to understand
its structure and internal working.

What is Orcha?
--------------
Orcha is an easy to use orchestrator for your projects. It provides
the basic structure to you to decide whether a petition must be run.

By itself, Orcha is capable of doing nothing - it is just the skeleton.
Instead, you need to develop and deploy your own plugins or create a
standalone application by using :ref:`Orcha's library<Library>`.

How it works?
-------------
Orcha provides a service running in the background and waiting
for petitions to come. It uses :mod:`Python's multiprocessing<multiprocessing>`
for handling petitions, queues and messages in inner process communication.

Internally, multiples queues and threads are spawned for moving messages,
assigning priorities and executing them in a safe way. More details can
be found at :mod:`orcha.lib` package.


Table of contents
=================

.. toctree::
   :maxdepth: 2
   :caption: First steps

   first-steps

.. toctree::
   :maxdepth: 2
   :caption: Plugins system

   plugins-structure
   develop-plugin

.. toctree::
   :maxdepth: 2
   :caption: Package documentation

   orcha


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
