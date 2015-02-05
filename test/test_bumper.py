import sys

from bumper import bump, BumpAccident
from bumper.utils import PyPI

import pytest
from test_stubs import temp_dir


def test_bump_no_file():
  with temp_dir():
    with pytest.raises(SystemExit):
      bump()


def test_bump_no_op():
  with temp_dir():
    with open('requirements.txt', 'w') as fp:
      fp.write('localconfig')

    bump()

    new_req = open('requirements.txt').read()
    assert 'localconfig' == new_req


def test_bump_latest():
  with temp_dir():
    with open('requirements.txt', 'w') as fp:
      fp.write('localconfig==0.0.1')

    bump()

    new_req = open('requirements.txt').read()
    expect_req = 'localconfig==%s\n' % PyPI.latest_module_version('localconfig')
    assert 'localconfig==0.0.1' != new_req
    assert expect_req == new_req


def test_bump_filter():
  with temp_dir():
    with open('requirements.txt', 'w') as fp:
      fp.write('localconfig==0.0.1\nremoteconfig==0.0.1')

    sys.argv = ['bump', 'remoteconfig']
    bump()

    new_req = open('requirements.txt').read()
    expect_req = 'localconfig==0.0.1\nremoteconfig==%s\n' % PyPI.latest_module_version('remoteconfig')
    assert expect_req == new_req


def test_bump_add():
  with temp_dir():
    with open('requirements.txt', 'w') as fp:
      fp.write('localconfig==0.0.1\nremoteconfig==0.0.1')

    sys.argv = ['bump', 'remoteconfig', 'requests', 'clicast>=0.2', '--add']
    bump()

    new_req = open('requirements.txt').read()
    expect_req = 'clicast>=0.2\nlocalconfig==0.0.1\nremoteconfig==%s\nrequests\n' % PyPI.latest_module_version('remoteconfig')
    assert expect_req == new_req


def test_bump_published_check():
  with temp_dir():
    orig_reqs = 'localconfig==0.0.1\nremoteconfig==0.0.1'

    with pytest.raises(BumpAccident) as e:
      with open('requirements.txt', 'w') as fp:
        fp.write(orig_reqs)

      sys.argv = ['bump', 'remoteconfig', 'requests', 'clicast>1000', '--add', '--debug']
      bump()

    assert 'no published versions' in str(e)

    reqs = open('requirements.txt').read()
    assert orig_reqs == reqs