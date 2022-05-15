CREATE TABLE Feed (feed_id TEXT PRIMARY KEY, account_no TEXT, body TEXT, publish_at TEXT, attachments TEXT, sent BOOLEAN);
CREATE TABLE Attachment (attachment_id TEXT PRIMARY KEY, type TEXT, url TEXT);
CREATE TABLE Artist (account_no TEXT PRIMARY KEY, nickname TEXT);