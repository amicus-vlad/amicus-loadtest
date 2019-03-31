import json
import logging
import uuid
from datetime import timedelta, datetime

import random
from random import randint
from tornado.escape import json_encode, json_decode
from tornado.gen import sleep
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop, PeriodicCallback

import settings

LOGGER = logging.getLogger(__name__)


class Client(object):
    def __init__(self, redis_client, donor,envelops):

        self.http_client = AsyncHTTPClient()
        self.redis_client =redis_client
        self.donor = donor
        self.envelops = envelops


    async def connect(self):
        login_endpoint = '{}/{}'.format(settings.WF_SERVER, 'api/v2/GC/login')

        payload = dict(password=self.donor.password,username=self.donor.email)
        req = HTTPRequest(login_endpoint, method='POST', headers={'Content-Type': 'application/json'},
                          body=json.dumps(payload))

        logged_in_donor = await self.http_client.fetch(req)
        auth_token = json.loads(logged_in_donor.body.decode()).get('Authorization')
        self.donor.auth_token = auth_token


        headers = {"Authorization":self.donor.auth_token, 'Content-Type': 'application/json'}
        self.headers = headers

        user_endpoint = '{}/{}'.format(settings.WF_SERVER, 'api/v2/GC/User/Admin/')

        user_endpoint = url_concat(user_endpoint, dict(user_name=self.donor.email))
        resp = await self.http_client.fetch(user_endpoint,headers={"Authorization":self.donor.auth_token})
        resp_body = json.loads((resp.body.decode()))
        user_data = resp_body['items'][0]['data']
        self.donor.object_id = user_data.get('object_id')
        self.donor.object_version = user_data.get('object_version')



        IOLoop.current().add_timeout(timedelta(seconds=random.uniform(0, 5)), self.add_fund)
        while True:
            await self.add_fund()
            await sleep(1)


    async def add_fund(self):
        envelope_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())

        payload = {
              "envelope_id":envelope_id,
              "ops": [
                {
                  "op": "/GC/Fund/GivingFund/add_new",
                  "params": {
                    "fund_creator_ref": {
                      "object_id": self.donor.object_id,
                      "object_version": self.donor.object_version
                    },
                    "fund_number": receipt_id,
                    "name": "fund_{}".format(receipt_id)
                  },
                  "receipt_id": receipt_id
                }
              ]
            }

        endpoint = '{}/{}'.format(settings.WF_SERVER, 'api/v2/GC/Fund/GivingFund/add_new')
        body = json_encode(payload)

        response = await self.http_client.fetch(endpoint,
                                                method="POST",
                                                body=body,
                                                headers=self.headers)
        if response.code == 200:
            LOGGER.info('Finished to search')
            self.envelops[envelope_id] = datetime.utcnow()
        else:
            LOGGER.info('Failed with search')

