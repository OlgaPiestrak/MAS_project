from os.path import abspath, dirname

from redis import Redis
from websocket_server import WebsocketServer

TOPICS = ['session_start', 'session_log', 'session_end']


def message_received(client, server, message):
    print(message)

    cert_file = dirname(abspath(__file__)) + '/cert.pem'
    redis = Redis(host='172.16.238.12', ssl=True, ssl_ca_certs=cert_file, password='changemeplease')

    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    mapping = dict.fromkeys(((message + '_' + t) for t in TOPICS),
                            lambda msg: server.send_message(client, msg['data'].decode()))
    pubsub.subscribe(**mapping)
    pubsub.run_in_thread(sleep_time=0.001)


socket_server = WebsocketServer(host='0.0.0.0', port=8004)
socket_server.set_fn_message_received(message_received)
socket_server.run_forever()
