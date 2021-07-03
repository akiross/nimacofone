#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="my_server",
    version="0.0.1",
    # Modules to import from other scripts:
    packages=find_packages(),
    # Executables
    scripts=["server.py"],
)
