import os
import sys

from bumper import bump, BumpAccident
from bumper.utils import PyPI

import pytest
from test_stubs import temp_dir


@pytest.fixture(autouse=True)
def mock_argv(monkeypatch):
    monkeypatch.setattr('sys.argv', ['bump'])


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
        expect_req = 'localconfig==%s\n' % PyPI.latest_package_version('localconfig')
        assert 'localconfig==0.0.1' != new_req
        assert expect_req == new_req


def test_bump_recursive():
    with temp_dir():
        with open('requirements.txt', 'w') as fp:
            fp.write('-r requirements/prod.txt\n')
            fp.write('localconfig==0.0.1')
        os.mkdir('requirements')
        with open('requirements/prod.txt', 'w') as fp:
            fp.write('localconfig==0.0.1')

        bump()

        new_req = open('requirements.txt').read()
        expect_req = '-r requirements/prod.txt\nlocalconfig==%s\n' % PyPI.latest_package_version('localconfig')
        assert 'localconfig==0.0.1' != new_req
        assert expect_req == new_req

        new_req = open('requirements/prod.txt').read()
        expect_req = 'localconfig==%s\n' % PyPI.latest_package_version('localconfig')
        assert 'localconfig==0.0.1' != new_req
        assert expect_req == new_req


def test_bump_bad_requirements():
    with temp_dir():
        with open('requirements.txt', 'w') as fp:
            fp.write('git+https://github.com/someversion@blah@blah=blah\n')
            fp.write('localconfig==0.0.1\n')
            fp.write('http://github.com/someversion@blah@blah=blah')

        bump()

        new_req = open('requirements.txt').read()
        expect_req = ('git+https://github.com/someversion@blah@blah=blah\n' +
                      'localconfig==%s\n' % PyPI.latest_package_version('localconfig') +
                      'http://github.com/someversion@blah@blah=blah\n')
        assert 'localconfig==0.0.1' != new_req
        assert expect_req == new_req


def test_bump_filter():
    with temp_dir():
        with open('requirements.txt', 'w') as fp:
            fp.write('localconfig==0.0.1\nremoteconfig==0.0.1')

        sys.argv = ['bump', 'remoteconfig']
        bump()

        new_req = open('requirements.txt').read()
        expect_req = 'localconfig==0.0.1\nremoteconfig==%s\n' % PyPI.latest_package_version('remoteconfig')
        assert expect_req == new_req


def test_bump_add():
    with temp_dir():
        with open('requirements.txt', 'w') as fp:
            fp.write('localconfig==0.0.1\nremoteconfig==0.0.1')

        sys.argv = ['bump', 'remoteconfig', 'requests', 'clicast>=0.2', '--add']
        bump()

        new_req = open('requirements.txt').read()
        expect_req = 'clicast>=0.2\nlocalconfig==0.0.1\nremoteconfig=={}\nrequests\n'.format(
            PyPI.latest_package_version('remoteconfig'))
        assert expect_req == new_req


def test_bump_add_detail():
    with temp_dir():
        with open('requirements.txt', 'w') as fp:
            fp.write('remoteconfig==0.0.1')

        with open('pinned.txt', 'w') as fp:
            fp.write('remoteconfig==0.0.1')

        sys.argv = ['bump', 'remoteconfig>0.2,<0.2.5', '--detail']
        bump()

        new_req = open('requirements.txt').read()
        expect_req = 'remoteconfig<0.2.5,>0.2\n'
        assert expect_req == new_req

        new_pinned = open('pinned.txt').read()
        expect_pinned = 'remoteconfig==0.2.4\n'
        assert expect_pinned == new_pinned


def test_bump_published_check():
    with temp_dir():
        orig_reqs = 'localconfig==0.0.1\nremoteconfig==0.0.1'

        with pytest.raises(BumpAccident) as e:
            with open('requirements.txt', 'w') as fp:
                fp.write(orig_reqs)

            sys.argv = ['bump', 'remoteconfig', 'requests', 'clicast>1000', '--add', '--debug']
            bump()

        assert 'No published version could satisfy the requirement(s): clicast>1000' in str(e)

        reqs = open('requirements.txt').read()
        assert orig_reqs == reqs
