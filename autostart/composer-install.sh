#!/usr/bin/env bash
apt-get -y update
apt-get install -y --fix-missing sshpass

cd /var/www/default
composer self-update && composer install --no-dev --no-suggest --no-progress --prefer-dist --optimize-autoloader

pip2 install redis hiredis
