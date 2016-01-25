import os
import json


def test_basic_index(index_path, project_path):
    from rigidsearch.search import index_tree, get_index

    with open(os.path.join(project_path, 'config.json'), 'rb') as f:
        cfg = json.load(f)

    log = list(index_tree(cfg, index_path=index_path,
                          base_dir=project_path))
    assert log

    content_id = 'e324d4f2e1a8a49c4efcc049b296d7b60bce4e7d'
    content_path = os.path.join(index_path, 'cur', 'content')
    with open(os.path.join(content_path, content_id)) as f:
        contents = f.read().strip()
        assert contents == 'Yo, this should totally be indexed.'

    index = get_index(index_path)
    results = index.search('totally', section='a')
    assert results['items'] == [{
        'excerpt': u'Yo, this should <strong class="match term0">'
                   u'totally</strong> be indexed',
        'path': u'index',
        'title': u'Hello World',
        'section': 'a'
    }]
