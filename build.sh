#!/bin/bash

DIR=$(dirname $(readlink -f "$0"))

cd "$DIR"

# --no-cache
docker build "$@" --tag irctelegram .
