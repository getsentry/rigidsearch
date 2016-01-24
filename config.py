import os
getenv = os.environ.get

SEARCH_INDEX_PATH = getenv('RIGIDSEARCH_SEARCH_INDEX_PATH', '/tmp/testindex')
SEARCH_INDEX_SECRET = getenv('RIGIDSEARCH_SEARCH_INDEX_SECRET',
                             '7b4f9fa0-82de-456b-bdc2-1a9cf32242e0')
