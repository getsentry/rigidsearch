FROM python:2.7

RUN mkdir -p /usr/src/rigidsearch
WORKDIR /usr/src/rigidsearch

COPY . /usr/src/rigidsearch
RUN pip install --no-cache-dir .

# This matches SEARCH_INDEX_PATH inside config.py
VOLUME /tmp/testindex
EXPOSE 5001
ENTRYPOINT ["/usr/src/rigidsearch/docker-entrypoint.sh"]
CMD ["--help"]
