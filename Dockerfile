FROM python:2.7

RUN mkdir -p /usr/src/rigidsearch
WORKDIR /usr/src/rigidsearch

COPY . /usr/src/rigidsearch
RUN pip install --no-cache-dir "file://`pwd`#egg=rigidsearch[server]"

ENV RIGIDSEARCH_CONFIG=/usr/src/rigidsearch/config.py \
    RIGIDSEARCH_SEARCH_INDEX_PATH=/var/lib/rigidsearch/index \
    RIGIDSEARCH_RUN_BIND=0.0.0.0:8000

VOLUME /var/lib/rigidsearch
EXPOSE 8000
ENTRYPOINT ["/usr/src/rigidsearch/docker-entrypoint.sh"]
CMD ["run"]
