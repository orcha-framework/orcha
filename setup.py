from setuptools import setup

setup(
    name="orcha",
    version="0.2.6-1",
    packages=[
        "orcha.bin",
        "orcha.exceptions",
        "orcha.interfaces",
        "orcha.lib",
        "orcha.plugins",
        "orcha.plugins.embedded",
        "orcha.utils",
        "orcha",
    ],
    url="https://github.com/Javinator9889/orcha",
    license="MIT",
    author="Javinator9889",
    author_email="jalonso@teldat.com",
    description="Orcha is an AIO orchestrator for your projects",
    entry_points={
        "console_scripts": [
            "orcha = orcha.bin.main:main",
        ]
    },
    python_requires=">=3.7",
)
