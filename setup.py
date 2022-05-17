from setuptools import setup

setup(
    name="orcha",
    version="0.1.9",
    packages=[
        "orcha.bin",
        "orcha.exceptions",
        "orcha.interfaces",
        "orcha.lib",
        "orcha.plugins",
        "orcha.utils",
        "orcha",
    ],
    url="",
    license="",
    author="Javinator9889",
    author_email="jalonso@teldat.com",
    description="Orcha is an AIO orchestrator for your projects",
    entry_points={
        "console_scripts": [
            "orcha = orcha.bin.main:main",
        ]
    },
)
