#!/usr/bin/env python
import json
import logging
import signal
import time
import uuid
from datetime import datetime

import tornado.httpserver
import tornado.ioloop
import tornado.web
from redis import Redis
from tornado.gen import sleep, multi
from tornado.httpclient import AsyncHTTPClient
from tornado.options import options
from tornado.httpclient import HTTPRequest


import settings
from settings import REDIS_SERVER, MAX_HTTP_CLIENTS

logger = logging.getLogger(__name__)



donors = []

envelops = {}

long_polling=True


def sig_handler(sig, frame):
    print('Caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback_from_signal(shutdown)


def shutdown():
    global long_polling
    long_polling=False
    print('Test runner will shutdown in %s seconds ...', 1)
    io_loop = tornado.ioloop.IOLoop.instance()

    deadline = time.time() + 1

    def stop_loop():
        now = time.time()
        if now < deadline and (io_loop._callbacks or io_loop._timeouts):
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            print('Shutdown')

    stop_loop()


class Donor(object):
    def __init__(self, email, name, password):

        self.email = email
        self.name = name
        self.password = password
        self.auth_token = None

    def to_json(self):
        return dict(
                    email=self.email,
                    password=self.password,
                    auth_token = self.auth_token)

def request(i):


    http_client = AsyncHTTPClient()

    endpoint = '{}/{}'.format(settings.WF_SERVER, 'api/v2/GC/User/Admin/add_new')
    auth_token = '2499752e-c025-45c1-a671-ffbfc99cd394'  # options.auth_token


    envelope_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())
    email = "test{}@gmail.com".format(i)
    name = "test{}".format(i)
    password = "123456"

    payload = {
        "envelope_id": envelope_id,
        "ops": [
            {
                "op": "/GC/User/Admin/add_new",
                "params": {
                    "email": email,
                    "name": name,
                    "password": password
                },
                "receipt_id": receipt_id
            }
        ]
    }

    donor = Donor(email, name, password)
    donors.append(donor)

    req = HTTPRequest(endpoint, method='POST', headers={'Authorization': auth_token,
                                                        'Content-Type': 'application/json'}, body=json.dumps(payload))

    logger.info("New donor:{}".format(donor.to_json()))
    future =  http_client.fetch(req)
    return future

async def create_donors(from_donor, to_donor):
    numbers_list = list(range(from_donor, to_donor))
    chunks = [numbers_list[i:i + 10] for i in range(from_donor, to_donor, 20)]

    for chunk in chunks:
        reqs = [request(i) for i in chunk]
        await multi(reqs)

    logger.info("done")

async def open_long_polling_connection():
    http_client = AsyncHTTPClient()
    continuation_token=None
    while long_polling:
        try:
            if continuation_token:
                response = await http_client.fetch("http://localhost:8888/api/v2/events/updates?object_type=Fund&object_sub_type=GivingFund&continuation_token={}".format(continuation_token))
            else:
                response = await http_client.fetch(
                    "http://localhost:8888/api/v2/events/updates?object_type=User&object_sub_type=Admin")
            data = json.loads(response.body.decode())
            logger.info("long_polling response:"+response.body.decode())
            if data:
                continuation_token = data['continuation_token']
                for msg in data['messages']:
                    envelope_id = msg['envelope_id']
                    current_time = datetime.utcnow()

                    round_trip_time = current_time - envelops[envelope_id]
                    logger.info("request time for {} is {}".format(envelope_id, round_trip_time))
        except:
            pass


async def init():

    AsyncHTTPClient.configure(None, max_clients=MAX_HTTP_CLIENTS)

    from test_client import Client

    redis_client = Redis(**REDIS_SERVER)


    process_num = options.process_num

    logger.info('process_num:{0}'.format(process_num))

    delay = settings.RAMP_UP / settings.CLIENT_NUM
    ioloop = tornado.ioloop.IOLoop.current()
    await create_donors(process_num*settings.CLIENT_NUM,settings.CLIENT_NUM*(process_num+1))
    for donor in donors:
        ioloop.add_callback(Client(redis_client, donor,envelops).connect)
        await sleep(delay)
    ioloop.add_callback(open_long_polling_connection)




def main():

    tornado.options.options.log_file_prefix = '/tmp/load_test.log'
    tornado.options.parse_command_line()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(init)
    logger.info("started")
    ioloop.start()
    logger.info("Exit...")


if __name__ == "__main__":
    main()
