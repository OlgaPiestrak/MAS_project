#!/usr/bin/env bash
cd /var/www/default
composer self-update
composer install --no-dev --no-suggest --no-progress --prefer-dist --optimize-autoloader
