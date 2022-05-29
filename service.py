import config
import universe
import sqlite3
import requests
import time
import os
import telegram
from telegram import InputMediaPhoto, InputMediaVideo

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

    if r.status_code != 200:
        return None

    f = open(file_path, "wb")
    f.write(r.content)
    f.close()
    return file_path

def save_video(aid, url):
    file_path = "{}{}.mp4".format(config.FNS_DATA_DIR, aid)
    if config.DEBUG >= 1:
        os.system("ffmpeg -y -i \"{}\" -c copy -bsf:a aac_adtstoasc {}".format(url, file_path))
    else:
        os.system("ffmpeg -y -i \"{}\" -c copy -bsf:a aac_adtstoasc {} > /dev/null 2>&1".format(url, file_path))
    if os.path.isfile(file_path):
        return file_path
    else:
        return None

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

    print("Process {}".format(feed.feed_id))
    id = feed.feed_id
    artist = feed.artist.account_no
    body = feed.body
    publish_at = feed.publish_date
    _img_attachment = []
    _vid_attachment = []
    for aid, attachment in feed.attachments.items():
        if attachment.type == "image":
            save_path = ""
            if config.DEBUG >= 1:
                print("[+] Attachment Found")
                print("  [-] File ", attachment.file)
                print("  [-] Type", attachment.type)
            while True:
                save_path = save_image(aid, attachment.file)
                if save_path:
                    break
                print("Cloudfront download error, retry in 5 secondes")
                time.sleep(5)
            if config.DEBUG < 2:
                sql_cursor.execute("INSERT INTO Attachment VALUES (?, 'image', ?)", (aid, save_path))
                _img_attachment.append((aid, save_path))
        elif attachment.type == "video":
            save_path = ""
            if config.DEBUG >= 1:
                print("[+] Attachment Found")
                print("  [-] File ", attachment.file)
                print("  [-] Type", attachment.type)
            while True:
                save_path = save_video(aid, attachment.file)
                if save_path:
                    break
                print("Cloudfront download error, retry in 5 secondes")
                time.sleep(5)

            if config.DEBUG < 2:
                sql_cursor.execute("INSERT INTO Attachment VALUES (?, 'video', ?)", (aid, save_path))
                _vid_attachment.append((aid, save_path))
    
    attachments = "|".join([t[0] for t in (_img_attachment + _vid_attachment)]) # concat aids

    if config.DEBUG < 2:
        sql_cursor.execute("INSERT INTO Feed VALUES (?, ?, ?, ?, ?, 0)", (id, artist, body, publish_at, attachments))
    return [t[1] for t in _img_attachment], [t[1] for t in _vid_attachment] #return file paths

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

    if config.DEBUG >= 1:
        print("[+] SEND_FEED called")
        print("  [-] MSG: ", msg)
        print("  [-] Image Attachment: ", ', '.join(data["images"]))
        print("  [-] Video Attachment: ", ', '.join(data["videos"]))
        if config.DEBUG == 2:
            return
    while True:
        try:
            if len(data["images"]) + len(data["videos"]) == 0:
                bot.sendMessage(chat_id = config.TELEGRAM_BOT_CHATID, text = msg)
            elif len(data["images"]) + len(data["videos"]) >= 2:
                media_group = []
                init = False
 
                if len(data["images"]) >= 1:
                    init = True
                    media_group.append(InputMediaPhoto(open(data["images"][0], 'rb'), caption = msg))
                    for img in data["images"][1:]:
                        media_group.append(InputMediaPhoto(open(img, 'rb'), caption = ''))
                if len(data["videos"]) >= 1:
                    rest_idx = 0
                    if not init:
                        media_group.append(InputMediaVideo(open(data["videos"][0], 'rb'), caption = msg))
                        rest_idx = 1
                    for img in data["videos"][rest_idx:]:
                        media_group.append(InputMediaVideo(open(img, 'rb'), caption = ''))

                bot.send_media_group(chat_id = config.TELEGRAM_BOT_CHATID, media = media_group)
            elif len(data["images"]) == 1:
                bot.send_photo(chat_id = config.TELEGRAM_BOT_CHATID, photo = open(data["images"][0], 'rb'), caption = msg) 
            elif len(data["videos"]) == 1:
                bot.send_video(chat_id = config.TELEGRAM_BOT_CHATID, video = open(data["videos"][0], 'rb'), caption = msg) 
        except Exception as e:
            print("Telegram Exception")
            print(e)
            time.sleep(1.5)
            continue
        break
    time.sleep(0.5)

def send_raw_feed(feed, img_attachments, vid_attachments):
    global fns_module

    data = {
        "nick": fns_module.artists[config.FNS_PLANET][feed.artist.account_no].nickname,
        "datetime": feed.publish_date,
        "body": feed.body,
        "images": img_attachments,
        "videos": vid_attachments
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
    img_attachments = []
    vid_attachments = []
    nickname = row[3]

    for aid in _attaches:
        sql_cursor.execute("SELECT type, url FROM Attachment WHERE attachment_id = ?", (aid,))
        if len(rows) == 0:
            continue
        row = rows[0]
        if row[0] == "image":
            img_attachments.append(row[1])
        elif row[1] == "video":
            vid_attachments.append(row[1])
    data = {
        "nick": nickname,
        "datetime": publish_at,
        "body": body,
        "images": img_attachments,
        "video": vid_attachments
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
    print("Hi?")
    while True:
        added, next = fns_module.LoadFeed(config.FNS_PLANET, next = next)
        if len(added) == 0:
            break
        feeds.extend(added)
    
    feeds.reverse()

    # process artists
    process_artists(fns_module.artists[config.FNS_PLANET])
    
    for f in feeds:
        img_attaches, vid_attaches = process_feed(f)
        fid = send_raw_feed(f, img_attaches, vid_attaches)
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
        img_attaches, vid_attaches = process_feed(f)
        fid = send_raw_feed(f, img_attaches, vid_attaches)
        mark_sent(fid)

    return len(feeds)
