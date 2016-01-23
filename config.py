PROCESSOR_TITLE_CLEANUP_FUNC = lambda x: x.split(u'\u2013')[0].strip()
PROCESSOR_CONTENT_SELECTORS = ['html|section.document']
PROCESSOR_IGNORE = ['.nocontent', 'html|a.headerlink', 'html|ul.breadcrumb']
INDEXER_DOCS_TO_IGNORE = ['sitemap', 'search']
SEARCH_INDEX_PATH = '/tmp/testindex'
