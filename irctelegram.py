#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job
from telegram.error import BadRequest
import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARN)

logger = logging.getLogger(__name__)


SERVER_NAME = "irctelegram.bridge"


def send(line):
    import sys
    sys.stdout.write(line.encode('utf-8'))
    sys.stdout.write("\n")


def flush():
    import sys
    sys.stdout.flush()


def safename(s):
    return s.replace(" ", "_").splitlines()[0]


def nickfromuser(fromuser):
    return safename(((fromuser.first_name or "_") + "_" + (fromuser.last_name or "_")).strip("_"))


def target_to_chat_id(target):
    if target.startswith("#") or target.startswith("+") or target.startswith("&"):
        return target[1:]
    return target


def on_msg(bot, update):
    fromuser = update.message.from_user
    ident = safename(fromuser.username) if fromuser.username else str(fromuser.id)
    nick = nickfromuser(fromuser)
    fromwho = nick + "!" + ident + "@" + str(fromuser.id) + "." + SERVER_NAME
    target = str(update.message.chat_id)
    if update.message.chat.type == "channel":
        target = "+" + target
    elif update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        target = "#" + target
    else:
        target = "&" + target
    before = ":" + fromwho + " PRIVMSG " + target + " :"
    for msg in update.message.text.splitlines():
        if update.message.forward_from:
            send(before + "Forwarded from " + nickfromuser(update.message.forward_from) + ": " + msg)
        else:
            send(before + msg)
    flush()


def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


def irc_parse(s):
    prefix = ''
    cmd = ''
    args = []
    s = s.rstrip("\r\n")
    if s:
        if s[0] == ':':
            prefix, s = s[1:].split(' ', 1)
        if s.find(' :') != -1:
            trailing = []
            s, trailing = s.split(' :', 1)
            args = s.split()
            args.append(trailing)
        else:
            args = s.split()
        cmd = args.pop(0)
    return prefix, cmd, args


def sendbotmsg(bot, chat_id, msg, parse_mode=None):
    try:
        if parse_mode:
            try:
                return bot.sendMessage(chat_id=chat_id, text=msg, parse_mode=parse_mode)
            except BadRequest as e:
                return bot.sendMessage(chat_id=chat_id, text=msg + "\n\n(Error: " + e.message + ")")
        else:
            return bot.sendMessage(chat_id=chat_id, text=msg)
    except BadRequest as e:
        send("X :Unable to send message; " + e.message)


def main():
    
    updater = None
    dp = None
    bot = None
    botnick = "bot"
    connected = False
    parse_mode = None
    
    try:
        send("X :Waiting for PASS with Telegram bot token")
        import sys
        while True:
            line = sys.stdin.readline()
            prefix, cmd_orig, args = irc_parse(line)
            cmd = cmd_orig.upper()
            if cmd == "PASS":
                if not updater:
                    updater = Updater(args[0])
                    dp = updater.dispatcher
                    bot = dp.bot
                    #dp.add_handler(CommandHandler("start", start))
                    dp.add_handler(MessageHandler([Filters.text], on_msg))
                    dp.add_error_handler(error) # log all errors
                    #updater.job_queue.put(Job(asdfasdf, 10, repeat=True, context=None))
                    updater.start_polling()
            elif cmd == "NICK":
                botnick = args[0]
                if not connected:
                    connected = True
                    send(":" + SERVER_NAME + " 001 " + botnick + " :Welcome to Telegram")
                    send((":" + SERVER_NAME + " 005 " + botnick + " NETWORK=Telegram CASEMAPPING=ascii" +
                        " CHANTYPES=#&!+ TPARSEMODE=IRC,HTML,Markdown NICKLEN=500 :are supported by this server"))
                    send(":" + SERVER_NAME + " 422 " + botnick + " :No MOTD")
            elif cmd == "USER":
                pass
            elif cmd == "JOIN":
                pass
            elif cmd == "PART":
                pass
            elif cmd == "PRIVMSG":
                if bot:
                    chat_id = target_to_chat_id(args[0])
                    if args[1].startswith("\1ACTION "):
                        sendbotmsg(bot, chat_id, " * " + args[1][8:].rstrip("\1"), parse_mode)
                    else:
                        sendbotmsg(bot, chat_id, args[1], parse_mode)
            elif cmd == "NOTICE":
                if bot:
                    sendbotmsg(bot, chat_id, "Notice: " + args[1], parse_mode)
            elif cmd == "PING":
                send(":" + SERVER_NAME + " PONG " + SERVER_NAME + " :" + (args[0] if len(args) else ""))
            elif cmd == "PONG":
                pass
            elif cmd == "TPARSEMODE":
                if len(args) > 0:
                    parse_mode = None if args[0].upper() == "IRC" else args[0]
                send(":" + SERVER_NAME + " 300 :" + ("IRC" if not parse_mode else parse_mode))
            elif cmd == "QUIT":
                send("X :Quit: " + ("" if len(args) == 0 else args[0]))
                break
            elif cmd:
                send(":" + SERVER_NAME + " 421 " + cmd + " :Unknown command")
            flush()
    except KeyboardInterrupt as e:
        send("X :Interrupted")
    except Exception as e:
        logger.error(e, exc_info=True)
        send("X :Error")
    
    if updater:
        flush()
        updater.stop()


if __name__ == '__main__':
    main()

