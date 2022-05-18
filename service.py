import config
import universe
import sqlite3
import requests
import time
import telegram
from telegram import InputMediaPhoto

fns_module = None
_sql_conn, sql_cursor = None, None
bot = None

def init():
    global fns_module
    global _sql_conn, sql_cursor
    global bot
    
    # initialize FNS module
    if config.UNIVERSE_MODE == "ACCESS":
        sess = universe.UserSession(access_token = config.UNIVERSE_ACCESS_TOKEN)
    elif config.UNIVERSE_MODE == "REFRESH":
        sess = universe.UserSession(refresh_token = config.UNIVERSE_REFRESH_TOKEN)    

    fns_module = universe.FNSModule(sess)
    
    # initialize sqlite connection
    _sql_conn = sqlite3.connect(config.FNS_DB, isolation_level = None)
    sql_cursor = _sql_conn.cursor()

    # initialize telegram bot
    bot = telegram.Bot(config.TELEGRAM_BOT_TOKEN)


def save_image(aid, url):
    file_path = "{}{}.jpeg".format(config.FNS_DATA_DIR, aid)
    r = requests.get(url, allow_redirects = True)
    f = open(file_path, "wb")
    f.write(r.content)
    f.close()
    return file_path

def is_new_feed(feed):
    global sql_cursor

    id = feed.feed_id
    sql_cursor.execute("SELECT 1 FROM Feed WHERE feed_id = ?", (id,))
    rows = sql_cursor.fetchall()

    if len(rows) != 0:
        return False
    else:
        return True

def process_feed(feed):
    global sql_cursor

    id = feed.feed_id
    artist = feed.artist.account_no
    body = feed.body
    publish_at = feed.publish_date
    _attachment = []
    for aid, attachment in feed.attachments.items():
        if attachment.type == "image":
            save_path = save_image(aid, attachment.file)
            sql_cursor.execute("INSERT INTO Attachment VALUES (?, 'image', ?)", (aid, save_path))
            _attachment.append((aid, save_path))
        else:
            #TODO: implement
            pass
    
    attachments = "|".join([t[0] for t in _attachment]) # concat aids

    sql_cursor.execute("INSERT INTO Feed VALUES (?, ?, ?, ?, ?, 0)", (id, artist, body, publish_at, attachments))
    return [t[1] for t in _attachment] #return file paths

def is_new_artist(artist):
    global sql_cursor

    ano = artist.account_no
    sql_cursor.execute("SELECT 1 FROM Artist WHERE account_no = ?", (ano,))
    rows = sql_cursor.fetchall()

    if len(rows) != 0:
        return False
    else:
        return True

def process_artists(artists):
    global sql_cursor
    for acc_no in artists:
        if not is_new_artist(artists[acc_no]):
            # already exists, update
            sql_cursor.execute("UPDATE Artist SET nickname = ? WHERE account_no = ?", (artists[acc_no].nickname, acc_no))
        else:
            # create artist
            sql_cursor.execute("INSERT INTO Artist VALUES (?, ?)", (acc_no, artists[acc_no].nickname))
        

def __send_feed(data):
    global bot
    msg = '[{}] ({})\n\n{}'.format(data["nick"], data["datetime"], data["body"]).strip()

    while True:
        try:
            if len(data["images"]) == 0:
                bot.sendMessage(chat_id = config.TELEGRAM_BOT_CHATID, text = msg)
            elif len(data["images"]) == 1:
                bot.send_photo(chat_id = config.TELEGRAM_BOT_CHATID, photo = open(data["images"][0], 'rb'), caption = msg)
            else:
                media_group = []
                media_group.append(InputMediaPhoto(open(data["images"][0], 'rb'), caption = msg))
                for img in data["images"][1:]:
                    media_group.append(InputMediaPhoto(open(img, 'rb'), caption = ''))
                bot.send_media_group(chat_id = config.TELEGRAM_BOT_CHATID, media = media_group)
        except:
            print("Telegram Exception")
            time.sleep(1.5)
            continue
        break
    time.sleep(0.5)

def send_raw_feed(feed, attachments):
    global fns_module

    data = {
        "nick": fns_module.artists[config.FNS_PLANET][feed.artist.account_no].nickname,
        "datetime": feed.publish_date,
        "body": feed.body,
        "images": attachments
    }
    
    __send_feed(data)

    return feed.feed_id

def send_feed(fid):
    global sql_cursor

    sql_cursor.execute("SELECT f.body, f.publish_at, f.attachments, a.nickname FROM Feed f JOIN Artist a ON f.account_no = a.account_no WHERE feed_id = ?", (fid,))
    rows = sql_cursor.fetchall()

    if len(rows) == 0:
        return
    row = rows[0]
    
    body = row[0]
    publish_at = row[1]
    _attaches = row[2].split('|')
    attachments = []
    nickname = row[3]

    for aid in _attaches:
        sql_cursor.execute("SELECT url FROM Attachment WHERE attachment_id = ?", (aid,))
        if len(rows) == 0:
            continue
        row = rows[0]
        attachments.append(row[0])
    
    data = {
        "nick": nickname,
        "datetime": publish_at,
        "body": body,
        "images": attachments
    }

    __send_feed(data)

    return fid

def sent_omits():
    global sql_cursor

    sql_cursor.execute("SELECT feed_id FROM Feed WHERE sent = 0")
    rows = sql_cursor.fetchall()

    fids = []
    for row in rows:
        fids.append(row[0])
        send_feed(row[0])

    return fids

def mark_sent(fid):
    global sql_cursor

    sql_cursor.execute("UPDATE Feed SET sent = 1 WHERE feed_id = ?", (fid,))

def load_prev():
    global fns_module

    next = 0.0
    
    feeds = []
    while True:
        added, next = fns_module.LoadFeed(config.FNS_PLANET, next = next)
        if len(added) == 0:
            break
        feeds.extend(added)
    
    feeds.reverse()

    # process artists
    process_artists(fns_module.artists[config.FNS_PLANET])
    
    for f in feeds:
        attaches = process_feed(f)
        fid = send_raw_feed(f, attaches)
        mark_sent(fid)


def update():
    # should be in while loop
    global fns_module
    
    next = 0.0

    feeds = []

    while True:
        escape = False
        added, next = fns_module.LoadFeed(config.FNS_PLANET, next = next)
        
        if len(added) == 0:
            break
        
        for feed in added:
            if is_new_feed(feed):
                feeds.append(feed)
            else:
                escape = True
                break
        
        if escape:
            break
    
    if len(feeds) == 0:
        return 0

    feeds.reverse()

    # process artists
    process_artists(fns_module.artists[config.FNS_PLANET])
    
    for f in feeds:
        attaches = process_feed(f)
        fid = send_raw_feed(f, attaches)
        mark_sent(fid)

    return len(feeds)
