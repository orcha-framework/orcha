#!/bin/env bash
# Helper script that installs all required dependencies
# and creates the documentation in the specified directory
set -euo pipefail

sudo apt-get install -y python3-pip python3-sphinx libsystemd-dev
pushd docs/

pip3 install -r requirements-docs.txt
make clean
make html
make man

popd
exit 0
