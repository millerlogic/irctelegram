#!/bin/bash

docker create \
  --restart unless-stopped \
  -p 127.0.0.1:28281:28281 \
  --name irctelegram \
  irctelegram
