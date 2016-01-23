FROM python:2.7

RUN mkdir -p /usr/src/rigidsearch
WORKDIR /usr/src/rigidsearch

COPY . /usr/src/rigidsearch
RUN pip install --no-cache-dir .

ENV RIGIDSEARCH_RUN_BIND=0.0.0.0:8000

# This matches SEARCH_INDEX_PATH inside config.py
VOLUME /tmp/testindex
EXPOSE 8000
ENTRYPOINT ["/usr/src/rigidsearch/docker-entrypoint.sh"]
CMD ["run"]
