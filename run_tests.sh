#!/bin/bash

# Ensure the script will exit with an error if a test fails
set -e

# Tests to run
#tox -e pep8
tox -e py27
