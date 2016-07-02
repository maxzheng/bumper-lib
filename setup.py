#!/usr/bin/env python

import setuptools


setuptools.setup(
  name='bumper-lib',
  version='0.2.17',

  author='Max Zheng',
  author_email='maxzheng.os @t gmail.com',

  description='A library to bump / pin your dependency requirements.',
  long_description=open('README.rst').read(),

  url='https://github.com/maxzheng/bumper-lib',

  install_requires=open('requirements.txt').read(),

  license='MIT',

  package_dir={'': 'src'},
  packages=setuptools.find_packages('src'),
  include_package_data=True,

  setup_requires=['setuptools-git'],

  classifiers=[
    'Development Status :: 5 - Production/Stable',

    'Intended Audience :: Developers',
    'Topic :: Software Development',

    'License :: OSI Approved :: MIT License',

    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
  ],

  keywords='library bump pin requirements requirements.txt pinned.txt',
)
