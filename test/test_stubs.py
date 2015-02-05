from contextlib import contextmanager
import os
import shutil
from tempfile import mkdtemp


@contextmanager
def temp_dir():
  try:
    cwd = os.getcwd()
    dtemp = mkdtemp()
    os.chdir(dtemp)

    yield dtemp

  finally:
    os.chdir(cwd)
    shutil.rmtree(dtemp)
