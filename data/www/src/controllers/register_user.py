from argparse import ArgumentParser
from os.path import abspath, dirname

from redis import Redis

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--username', type=str, help='Username')
    parser.add_argument('--password', type=str, help='Password')
    args = parser.parse_args()

    cert_file = dirname(abspath(__file__)) + '/cert.pem'
    # FIXME: use server-env or similar on actual cloud for authentication
    redis = Redis(host='172.16.238.12', ssl=True, ssl_ca_certs=cert_file, password='changemeplease')
    pipe = redis.pipeline()
    pipe.acl_setuser(enabled=True, username=args.username, passwords=['+' + args.password],
                     categories=['+@all', '-@dangerous'], keys=['user:' + args.username, args.username + '-*',
                                                                'emotion_detection', 'intent_detection',
                                                                'people_detection', 'face_recognition',
                                                                'robot_memory'])
    pipe.acl_save()
    print(pipe.execute())
    redis.close()
