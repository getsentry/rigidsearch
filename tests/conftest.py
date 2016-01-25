import pytest

import os
import shutil
import tempfile


@pytest.fixture(scope='function')
def index_path(request):
    path = tempfile.mkdtemp()

    def cleanup():
        try:
            shutil.rmtree(path)
        except (OSError, IOError):
            pass

    request.addfinalizer(cleanup)

    return path


@pytest.fixture(scope='module')
def project_path():
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), 'proj')
