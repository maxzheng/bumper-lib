from bumper.cars import AbstractBumper


class TestAbstractBumper(object):
  def test_requirements_for_changes(self):

    reqs_str = lambda changes: str([str(r) for r in AbstractBumper.requirements_for_changes(changes)])

    # assert "['localconfig']" == reqs_str(['Require localconfig'])
    # assert "['localconfig', 'remoteconfig>0.2', 'requests>=2.5']" == reqs_str(['* Require localconfig, remoteconfig>0.2, requests>=2.5'])

    # assert "['localconfig==1.2.3']" == reqs_str(['Pin localconfig==1.2.3'])

    # assert "['localconfig==1.2.3']" == reqs_str(['Bump localconfig to 1.2.3'])
    # assert "['localconfig==1.2.3', 'remoteconfig==2.3']" == reqs_str(['Bump localconfig to 1.2.3, remoteconfig to 2.3'])

    assert "['localconfig']" == reqs_str(['require=localconfig'])
    assert "['localconfig', 'remoteconfig==2.3']" == reqs_str(['require=localconfig,remoteconfig==2.3'])
    assert "['localconfig', 'remote-config==2.3']" == reqs_str(['requires=localconfig,remote-config==2.3'])
