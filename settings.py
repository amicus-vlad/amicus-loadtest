from tornado.options import define, parse_command_line


define("process_num", default=0, type=int)
define("auth_token", type=str)

parse_command_line()

WF_SERVER = 'http://localhost:5555'
CLIENT_NUM = 100
RAMP_UP = 5

RANDOM_SELECTION = True

MAX_HTTP_CLIENTS = 100

POLLING_TIME_DELTA = 60

HEARTBEAT_PERIOD = 10

REDIS_SERVER = dict(host='localhost', port=6379,db=0, decode_responses=True)

