#!/usr/bin/env python

import setuptools


setuptools.setup(
  name='bumper-lib',
  version='2.0.4',

  author='Max Zheng',
  author_email='maxzheng.os@gmail.com',

  description='A library to bump / pin your dependency requirements.',
  long_description=open('README.rst').read(),

  url='https://github.com/maxzheng/bumper-lib',

  install_requires=open('requirements.txt').read(),

  license='MIT',

  packages=setuptools.find_packages(),
  include_package_data=True,

  setup_requires=['setuptools-git', 'wheel'],

  classifiers=[
    'Development Status :: 5 - Production/Stable',

    'Intended Audience :: Developers',
    'Topic :: Software Development',

    'License :: OSI Approved :: MIT License',

    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
  ],

  keywords='library bump pin requirements requirements.txt pinned.txt',
)
