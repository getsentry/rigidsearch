import os
getenv = os.environ.get

PROCESSOR_TITLE_CLEANUP_REGEX = ur'^(.*?)\s+\u2013'
PROCESSOR_CONTENT_SELECTORS = getenv('RIGIDSEARCH_PROCESSOR_CONTENT_SELECTORS', 'section.document').split(',')
PROCESSOR_IGNORE = getenv('RIGIDSEARCH_PROCESSOR_IGNORE', '.nocontent,a.headerlink,ul.breadcrumb').split(',')
INDEXER_DOCS_TO_IGNORE = getenv('RIGIDSEARCH_INDEXER_DOCS_TO_IGNORE', 'sitemap,search').split(',')
SEARCH_INDEX_PATH = getenv('RIGIDSEARCH_SEARCH_INDEX_PATH', '/tmp/testindex')
