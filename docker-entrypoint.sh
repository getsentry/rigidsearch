#!/bin/bash
set -e

# If we are only passing a flag argument, assume it should be
# tacked onto the `rigidsearch` command.
if [ "${1:0:1}" = '-' ]; then
    set -- rigidsearch "$@"
fi

# If $1 isn't `rigidsearch`, let's first check if we're trying to execute
# a `rigidsearch` subcommand by checking `rigidsearch "$1" --help`.
if [ "$1" != 'rigidsearch' ] && rigidsearch "$1" --help > /dev/null 2>&1; then
    set -- rigidsearch "$@"
fi

exec "$@"
