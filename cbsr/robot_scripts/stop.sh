#!/usr/bin/env bash
cd "$(dirname "$0")"

[ ! -f video_producer.pid ] || pkill -F video_producer.pid
[ ! -f event_producer.pid ] || pkill -F event_producer.pid
[ ! -f audio_producer.pid ] || pkill -F audio_producer.pid
[ ! -f action_consumer.pid ] || pkill -F action_consumer.pid
[ ! -f audio_consumer.pid ] || pkill -F audio_consumer.pid
[ ! -f tablet.pid ] || pkill -F tablet.pid
[ ! -f puppet.pid ] || pkill -F puppet.pid

rm -f *.pid *.log
echo "Disconnected!"
