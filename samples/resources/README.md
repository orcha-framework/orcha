# Orcha Resource

Orcha Resource is a simple Orcha plugin that manages shared resources that
require mutual exclusion and allows clients to reserve and release resources.

# Installing

```
pip install .
```

# Running

## Server

```
orcha --key 1 serve resource <resources>
```

## Client

```
orcha --key 1 run resource <resource> <duration>
```
