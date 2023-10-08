# Orcha Docker

Orcha Docker is a simple Orcha plugin that can run commands in Docker
containers. The focus of this example is on petition lifecycle management.

# Installing

```
pip install docker
pip install .
```

# Running

## Server

```
orcha --key 1 serve docker
```

## Client

```
orcha --key 1 run docker <image> <command> [mount...]
```
