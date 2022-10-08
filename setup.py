#!/usr/bin/env python
# coding: utf-8

from setuptools import setup
from system_manager.version import __version__, __author__
from pathlib import Path
import re


readme = Path('README.md').read_text()
version = __version__
readme = re.sub(r"Version: [0-9]*\.[0-9]*\.[0-9][0-9]*", f"Version: {version}", readme)
print(f"README: {readme}")
with open("README.md", "w") as readme_file:
    readme_file.write(readme)
description = 'Synchronize your subtitle files by shifting the subtitle time (+/-)'

setup(
    name='system-manager',
    version=f"{version}",
    description=description,
    long_description=f'{readme}',
    long_description_content_type='text/markdown',
    url='https://github.com/Knucklessg1/system-manager',
    author=__author__,
    author_email='knucklessg1@gmail.com',
    license='Unlicense',
    packages=['system_manager'],
    include_package_data=True,
    install_requires=[],
    py_modules=['system_manager'],
    package_data={'system_manager': ['system_manager']},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: Public Domain',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    entry_points={'console_scripts': ['system-manager = system_manager.system_manager:main']},
)
