#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job
import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARN)

logger = logging.getLogger(__name__)


def send(line):
    import sys
    sys.stdout.write(line)
    sys.stdout.write("\n")


def flush():
    import sys
    sys.stdout.flush()


def safename(s):
    return s.replace(" ", "_").splitlines()[0]


def nickfromuser(fromuser):
    return safename(((fromuser.first_name or "_") + "_" + (fromuser.last_name or "_")).strip("_"))


def on_msg(bot, update):
    fromuser = update.message.from_user
    ident = safename(fromuser.username) if fromuser.username else str(fromuser.id)
    nick = nickfromuser(fromuser)
    fromwho = nick + "!" + ident + "@" + str(fromuser.id) + ".telegram"
    before = ":" + fromwho + " PRIVMSG " + str(update.message.chat_id) + " :"
    for msg in update.message.text.splitlines():
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


def main():
    
    updater = None
    dp = None
    bot = None
    botnick = "bot"
    connected = False
    
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
                    send(":telegram 001 " + botnick + " :Welcome to Telegram")
                    send(":telegram 005 " + botnick + " NETWORK=Telegram CASEMAPPING=ascii :are supported by this server")
                    send(":telegram 422 " + botnick + " :No MOTD")
            elif cmd == "PRIVMSG":
                if bot:
                    if args[1].startswith("\1ACTION "):
                        bot.sendMessage(chat_id=args[0], text=" * " + args[1][8:].rstrip("\1"))
                    else:
                        bot.sendMessage(chat_id=args[0], text=args[1])
            elif cmd == "NOTICE":
                if bot:
                    bot.sendMessage(chat_id=args[0], text="Notice: " + args[1])
            elif cmd == "QUIT":
                send("X :Quit: " + ("" if len(args) == 0 else args[0]))
                break
            elif cmd:
                send(":telegram 421 " + cmd + " :Unknown command")
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

