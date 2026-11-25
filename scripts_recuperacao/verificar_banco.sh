#!/bin/sh
set -eu
test "$(cat /dados/.sentico_v14_recovery_ready)" = 'SENTICO_V14_RECOVERY_GREEN_SYNC_TRIAL'
test "$(cat /dados/PG_VERSION)" = '17'
