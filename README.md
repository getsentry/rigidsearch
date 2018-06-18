# RigidSearch

A simple search API server that will be used for the sentry docs.

To run rigidsearch locally:

`mkvirtualenv rigidsearch`

`pip install —e .`

`rigidsearch devserver`


### RigidSearch + Sentry Docs
If you want to test searching on the sentry docs content, you need to send that content to your local rigidsearch server.
1. Have your rigidsearch server running (`rigidsearch devserver`)
2. In sentry-docs export the **RIGIDSEARCH_SERVER** and **RIGIDSEARCH_SECRET**

    `export RIGIDSEARCH_SERVER='http://127.0.0.1:5001/`
    
    `export RIGIDSEARCH_SECRET='supersecretnotreallythough'`
    
3. In sentry-docs upload the index `./bin/upload-search-index` - you should see the files being updated/index.

Then within rigidsearch you should be able to search either using the browser, or cli.

`http://localhost:5001/api/search?q=javascript&page=1&section=hosted`

`rigidsearch search --section=hosted javascript`

RigidSearch uses [Whoosh](http://whoosh.readthedocs.io) for the search engine.
