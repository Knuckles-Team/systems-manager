#!/usr/bin/env python
# coding: utf-8

from setuptools import setup
from systems_manager.version import __version__, __author__
from pathlib import Path
import re


readme = Path('README.md').read_text()
version = __version__
readme = re.sub(r"Version: [0-9]*\.[0-9]*\.[0-9][0-9]*", f"Version: {version}", readme)
print(f"README: {readme}")
with open("README.md", "w") as readme_file:
    readme_file.write(readme)
description = 'Systems-Manager will update your system and install/upgrade applications.'

setup(
    name='systems-manager',
    version=f"{version}",
    description=description,
    long_description=f'{readme}',
    long_description_content_type='text/markdown',
    url='https://github.com/Knucklessg1/system-manager',
    author=__author__,
    author_email='knucklessg1@gmail.com',
    license='Unlicense',
    packages=['systems_manager'],
    include_package_data=True,
    install_requires=[],
    py_modules=['systems_manager'],
    package_data={'systems_manager': ['systems_manager']},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: Public Domain',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    entry_points={'console_scripts': ['systems-manager = systems_manager.systems_manager:main']},
)
