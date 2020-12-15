from argparse import ArgumentParser
from os import getenv
from os.path import abspath, dirname

from redis import Redis

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--username', type=str, help='Username', default='default')
    parser.add_argument('--password', type=str, help='Password', default='changemeplease')
    parser.add_argument('--identifier', type=str, help='The camera device identifier')
    parser.add_argument('--command', type=str, help='Start or Stop')
    args = parser.parse_args()

    host = getenv('DB_IP')
    password = getenv('DB_PASS')
    self_signed = getenv('DB_SSL_SELFSIGNED')
    if self_signed == '1':
        cert_file = dirname(abspath(__file__)) + '/cert.pem'
        redis = Redis(host=host, ssl=True, ssl_ca_certs=cert_file, password=password)
    else:
        redis = Redis(host=host, ssl=True, password=password)

    if args.command == 'start':
        pipe = redis.pipeline()
        pipe.publish('stream_video', args.identifier)
        pipe.publish(args.identifier + '_action_video', '0')
        pipe.execute()
    else:
        redis.publish(args.identifier + '_action_video', '-1')
    redis.close()
