from quart import Quart, jsonify, request
from scrapper import Scrapper
import sys
import util

LOCALHOST = 'localhost'
PORT = 80

app = Quart(__name__)
scrapper = Scrapper()


@app.route('/')
async def hello():
    return 'hello'


@app.route('/departures')
async def departures():
    stop = request.args.get('stop')
    return jsonify(await scrapper.get_departures(stop))


def app_start() -> None:
    util.log('starting the app')
    args = sys.argv
    host = args[1] if len(args) > 1 else LOCALHOST
    port = int(args[2]) if len(args) > 2 else PORT
    app.run(host=host, port=port)


if __name__ == '__main__':
    app_start()
