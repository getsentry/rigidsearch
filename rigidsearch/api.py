from flask import Blueprint, jsonify, request

from rigidsearch.search import get_index
from rigidsearch.utils import cors


bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/search')
@cors()
def search():
    q = request.args.get('q') or u''
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    section = request.args.get('section') or 'generic'

    return jsonify(get_index().search(
        q, section, page=page, per_page=per_page))
