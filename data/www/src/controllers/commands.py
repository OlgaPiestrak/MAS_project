from argparse import ArgumentParser
from os import getenv
from os.path import abspath, dirname

from redis import Redis

import logging
import os

LOG_PATH = '/logs/log.csv'
LOG_CMD = 'log'

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--username', type=str, help='Username', default='default')
    parser.add_argument('--password', type=str, help='Password', default='changemeplease')
    parser.add_argument('--identifier', type=str, help='The target device identifier')
    parser.add_argument('--command', type=str, help='The name of the command')
    parser.add_argument('--data', type=str, help='The accompanying data')
    args = parser.parse_args()

    host = getenv('DB_IP')
    password = getenv('DB_PASS')
    self_signed = getenv('DB_SSL_SELFSIGNED')
    if self_signed == '1':
        cert_file = dirname(abspath(__file__)) + '/cert.pem'
        redis = Redis(host=host, ssl=True, ssl_ca_certs=cert_file, password=password)
    else:
        redis = Redis(host=host, ssl=True, password=password)

    logging.basicConfig(filename=os.path.dirname(os.path.realpath(__file__)) + LOG_PATH, filemode='a', format='%(asctime)s;%(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M')
    logging.info(args.command + ';' + args.data)

    if args.command != LOG_CMD:
        redis.publish(args.identifier + '_' + args.command, args.data)
    redis.close()
