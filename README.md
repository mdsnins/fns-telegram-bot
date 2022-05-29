# fns-telegram-bot
Telegram bot implementation of UNIVERSE FNS<br>
For detail about UNIVERSE implementation, please refer [py-universe](https://github.com/mdsnins/py-universe)

# Requirements

1. [py-universe](https://github.com/mdsnins/py-universe)
2. python-telegram-bot
3. ffmpeg

## Configuration

1. Write `config.py` referring  [config.py.sample](./config.py.sample)
2. Clone [py-universe](https://github.com/mdsnins/py-universe) and copy the whole `universe` directory
3. Write `config.py` of `py-universe`. For detail, please check `py-universe` repo.
4. Create proper directory for the data and set the permission correctly
5. Create SQLite3 database using [setup.sql](./setup.sql)
6. Load previous FNS articles using `python3 bootstrap.py load_prev`
7. Run the bot using `python3 bootstrap.py run_bot`

## Caution
- Only for studying and personal using, never for commercial.
- This doesn't include any secret credentials, they could be found in several way.
