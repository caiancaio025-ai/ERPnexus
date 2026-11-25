#!/bin/sh
set -eu
[ "$(cat /dados/PG_VERSION)" = '17' ]
test -d /dados/base
test -d /dados/global
test -f /dados/global/pg_control
