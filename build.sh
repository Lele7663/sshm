#!/bin/bash

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build the package
python setup.py sdist bdist_wheel

# Install locally with pipx for testing
pipx install --force ./dist/sshm-*.whl

echo "Package installed with pipx. You can now run 'sshm' from anywhere." 