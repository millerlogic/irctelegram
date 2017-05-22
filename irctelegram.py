#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job
from telegram.error import BadRequest
import time
import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARN)

logger = logging.getLogger(__name__)


SERVER_NAME = "irctelegram.bridge"

caps_supported = ["extended-join", "account-notify"]
caps_enabled = []
nicklists = {}


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
    if fromuser.username:
        return safename(fromuser.username)
    return safename(((fromuser.first_name or "_") + "_" + (fromuser.last_name or "_")).strip("_"))


def target_to_chat_id(target):
    if target.startswith("#") or target.startswith("+") or target.startswith("&"):
        return target[1:]
    return target


def get_msg_info(bot, update):
    fromuser = update.message.from_user
    account = safename(fromuser.username) if fromuser.username else str(fromuser.id)
    nick = nickfromuser(fromuser)
    fromwho = nick + "!" + str(fromuser.id) + "@" + account + "." + SERVER_NAME
    target = str(update.message.chat_id)
    if update.message.chat.type == "channel":
        target = "+" + target
    elif update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        target = "#" + target
    else:
        target = "&" + target
    fullname = ((fromuser.first_name or "") + " " + (fromuser.last_name or "")).strip()
    return nick, fromwho, target, account, fullname


def see_user(nick, fromwho, target, account, fullname):
    ltarget = target.lower()
    nl = nicklists.get(ltarget)
    if not nl:
        nl = {}
        nicklists[ltarget] = nl
    lnick = nick.lower()
    nickinfo = nl.get(lnick)
    if not nickinfo:
        nickinfo = {}
        nl[lnick] = nickinfo
        if "extended-join" in caps_enabled:
            xacct = account if account else "*"
            xfullname = fullname if fullname else ""
            send(":" + fromwho + " JOIN " + target + " " + xacct + " :" + xfullname)
        else:
            send(":" + fromwho + " JOIN " + target)
    nickinfo["nick"] = nick
    #nickinfo["addr"] = fromwho
    #nickinfo["fname"] = fullname


def on_msg(bot, update):
    nick, fromwho, target, account, fullname = get_msg_info(bot, update)
    see_user(nick, fromwho, target, account, fullname)
    before = ":" + fromwho + " PRIVMSG " + target + " :"
    for msg in update.message.text.splitlines():
        if update.message.forward_from:
            send(before + "Forwarded from " + nickfromuser(update.message.forward_from) + ": " + msg)
        else:
            send(before + msg)
    flush()


def on_sticker(bot, update):
    nick, fromwho, target, account, fullname = get_msg_info(bot, update)
    see_user(nick, fromwho, target, account, fullname)
    sticker = update.message.sticker
    sticker_id = sticker.file_id
    send(":" + fromwho + " PRIVMSG " + target + " :\1TELEGRAM-STICKER " + str(sticker_id) + "\1")
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


import re
# Note: this does not remove bold (x02) or reset (x0F), as we will handle them.
irc_parse_rex = re.compile("\x1f|\x12|\x16|\x03(?:\\d{1,2}(?:,\\d{1,2})?)?", re.UNICODE)
irc_handle_rex = re.compile("\x02|\x0F", re.UNICODE)


def ircToHTML(msg):
    xmsg = irc_parse_rex.sub("", msg)
    import cgi
    xmsg = cgi.escape(xmsg)
    state = {"bold":False}
    def handlebold(x):
        if x == "\x0F":
            if state["bold"]:
                state["bold"] = False
                return "</b>"
            return ""
        if x == "\x02":
            if state["bold"]:
                state["bold"] = False
                return "</b>"
            state["bold"] = True
            return "<b>"
    xmsg = irc_handle_rex.sub(lambda m: handlebold(m.group()), xmsg)
    if state["bold"]:
        xmsg += "</b>"
        #state["bold"] = False
    return xmsg


def sendbotmsg(bot, chat_id, msg, parse_mode=None):
    try:
        if parse_mode:
            try:
                xparsemode = parse_mode
                xmsg = msg
                if xparsemode.upper() == "IRC":
                    xmsg = ircToHTML(xmsg)
                    xparsemode = "HTML"
                return bot.sendMessage(chat_id=chat_id, text=xmsg, parse_mode=xparsemode)
            except BadRequest as e:
                return bot.sendMessage(chat_id=chat_id, text=msg + "\n\n(Error: " + e.message + ")")
        else:
            return bot.sendMessage(chat_id=chat_id, text=msg)
    except Exception as e:
        send("X :Unable to send message: " + repr(e))
        return False


def sendbotsticker(bot, chat_id, sticker):
    try:
        try:
            return bot.sendSticker(chat_id=chat_id, sticker=sticker)
        except BadRequest as e:
            return bot.sendMessage(chat_id=chat_id, text="(sticker)\n\n(Error: " + e.message + ")")
    except Exception as e:
        send("X :Unable to send sticker: " + repr(sticker))
        return False


def main():
    
    updater = None
    dp = None
    bot = None
    botnick = "bot"
    connected = False
    parse_mode = "IRC"
    tsleep = 0
    batching = False
    batchtarget = ""
    batchmsg = ""

    try:
        send("X :Waiting for PASS with Telegram bot token")
        import sys
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            prefix, cmd_orig, args = irc_parse(line)
            cmd = cmd_orig.upper()
            chat_id = None # make sure this isn't set to the old value.
            anywork = True
            if cmd == "PASS":
                if not updater:
                    updater = Updater(args[0])
                    dp = updater.dispatcher
                    bot = dp.bot
                    botnick = bot.username or botnick
                    #dp.add_handler(CommandHandler("start", start))
                    dp.add_handler(MessageHandler([Filters.text], on_msg))
                    dp.add_handler(MessageHandler([Filters.command], on_msg))
                    dp.add_handler(MessageHandler([Filters.sticker], on_sticker))
                    dp.add_error_handler(error) # log all errors
                    #updater.job_queue.put(Job(asdfasdf, 10, repeat=True, context=None))
                    updater.start_polling()
            elif cmd == "NICK":
                #botnick = args[0]
                if not connected:
                    connected = True
                    send(":" + SERVER_NAME + " 001 " + botnick + " :Welcome to Telegram")
                    send((":" + SERVER_NAME + " 005 " + botnick + " NETWORK=Telegram CASEMAPPING=ascii" +
                        " CHANTYPES=#&!+ TPARSEMODE=IRC,Plain,HTML,Markdown NICKLEN=500 TSLEEP TBATCHMSG :are supported by this server"))
                    send(":" + SERVER_NAME + " 422 " + botnick + " :No MOTD")
            elif cmd == "TSLEEP":
                if len(args) > 0:
                    tsleep = float(args[0])
                send(":" + SERVER_NAME + " 300 " + cmd + " :" + str(tsleep))
            elif cmd == "USER":
                anywork = False
            elif cmd == "JOIN":
                anywork = False
            elif cmd == "PART":
                anywork = False
            elif cmd == "BATCH":
                anywork = False
                try:
                    if batching and batchtarget and batchmsg:
                        sendbotmsg(bot, batchtarget, batchmsg, parse_mode)
                        anywork = True
                finally:
                    batching = False
                    batchtarget = ""
                    batchmsg = ""
                if len(args) >= 2 and args[0][0] == '+' and args[1] == SERVER_NAME + "/TBATCHMSG":
                    batching = True
            elif cmd == "PRIVMSG":
                if bot:
                    chat_id = target_to_chat_id(args[0])
                    msg = args[1]
                    sticker = msg[18:].rstrip("\1") if msg.startswith("\1TELEGRAM-STICKER ") else None
                    if batching:
                        if not batchtarget:
                            batchtarget = chat_id
                        if sticker is not None or batchtarget != chat_id:
                            try:
                                sendbotmsg(bot, batchtarget, batchmsg, parse_mode)
                            finally:
                                batching = False
                                batchtarget = ""
                                batchmsg = ""
                    if sticker is not None:
                        msg = ""
                        sendbotsticker(bot, chat_id, sticker)
                    elif args[1].startswith("\1ACTION "):
                        msg = args[1][8:].rstrip("\1")
                    if msg:
                        if batchtarget == chat_id:
                            if batchmsg:
                                batchmsg += "\n" + msg
                            else:
                                batchmsg = msg
                            anywork = False
                        else:
                            sendbotmsg(bot, chat_id, msg, parse_mode)
            elif cmd == "NOTICE":
                if bot:
                    chat_id = target_to_chat_id(args[0])
                    sendbotmsg(bot, chat_id, "Notice: " + args[1], parse_mode)
            elif cmd == "PING":
                send(":" + SERVER_NAME + " PONG " + SERVER_NAME + " :" + (args[0] if len(args) else ""))
            elif cmd == "PONG":
                pass
            elif cmd == "TPARSEMODE":
                if len(args) > 0:
                    parse_mode = None if args[0].upper() == "PLAIN" else args[0]
                send(":" + SERVER_NAME + " 300 " + cmd + " :" + ("Plain" if not parse_mode else parse_mode))
            elif cmd == "QUIT":
                send("X :Quit: " + ("" if len(args) == 0 else args[0]))
                break
            elif cmd == "CAP":
                subcmd = args[0].upper() if len(args) > 0 else ""
                if subcmd == "LS":
                    # List supported caps.
                    send("CAP " + botnick + " ACK :" + " ".join(caps_supported))
                elif subcmd == "REQ":
                    # Doesn't bother with capability modifiers.
                    new_caps_str = args[1] if len(args) > 1 else ""
                    new_caps = new_caps_str.split()
                    okcaps = True
                    if new_caps:
                        for newcap in new_caps:
                            if newcap not in caps_supported:
                                okcaps = False
                                break
                        if okcaps:
                            for newcap in new_caps:
                                if newcap not in caps_enabled:
                                    caps_enabled.append(newcap)
                    if okcaps:
                        send("CAP " + botnick + " ACK :" + new_caps_str)
                    else:
                        send("CAP " + botnick + " NAK :" + new_caps_str)
                elif subcmd == "LIST":
                    # List enabled caps.
                    send("CAP " + botnick + " ACK :" + " ".join(caps_enabled))
                elif subcmd == "END":
                    pass
                else:
                    send(":" + SERVER_NAME + " 410 " + (args[0].partition(' ')[0] if len(args) > 0 else "") + " :Invalid CAP subcommand")
                anywork = False
            elif cmd == "":
                anywork = False
            else:
                send(":" + SERVER_NAME + " 421 " + cmd + " :Unknown command")
            flush()
            if anywork:
                time.sleep(tsleep)
    except KeyboardInterrupt as e:
        send("X :Interrupted")
    except Exception as e:
        logger.error(e, exc_info=True)
        send("X :Error")
    finally:
        if updater:
            updater.stop()
            flush()


if __name__ == '__main__':
    main()

