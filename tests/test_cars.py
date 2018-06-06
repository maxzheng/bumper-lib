from bumper.cars import AbstractBumper


class TestAbstractBumper(object):
    def test_requirements_for_changes(self):

        def reqs_str(changes):
            return str([str(r) for r in AbstractBumper.requirements_for_changes(changes)])

        assert "['localconfig']" == reqs_str(['require=localconfig'])
        assert "['localconfig', 'remoteconfig==2.3']" == reqs_str(['require=localconfig,remoteconfig==2.3'])
        assert "['localconfig', 'remote-config==2.3']" == reqs_str(['requires=localconfig,remote-config==2.3'])
