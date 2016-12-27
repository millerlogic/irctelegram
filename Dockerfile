FROM gliderlabs/alpine:3.3

RUN apk update
RUN apk upgrade

RUN apk add python
RUN apk add gcc linux-headers musl-dev
RUN apk add python-dev
RUN apk add py-pip
RUN apk add libffi-dev py-cffi
RUN apk add openssl-dev

RUN pip install --upgrade --ignore-installed pip
RUN pip install python-telegram-bot --upgrade
RUN pip install urllib3 --upgrade
RUN pip install 'requests[security]' --upgrade # important for SSL

RUN mkdir /etc/irctelegram
ADD irctelegram.py /etc/irctelegram
ADD irctelegram_inetd.conf /etc/irctelegram
ADD irctelegram_service.sh /etc/irctelegram

RUN echo "irctelegram 28281/tcp" >>/etc/services

RUN addgroup -g 22101 irctelegram || true
RUN adduser -u 22101 -G irctelegram irctelegram || true

CMD [ "/etc/irctelegram/irctelegram_service.sh" ]

EXPOSE 28281
