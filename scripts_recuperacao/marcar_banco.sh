#!/bin/sh
set -eu
test "$(cat /dados/PG_VERSION)" = '17'
printf '%s\n' SENTICO_V14_RECOVERY_GREEN_SYNC_TRIAL > /dados/.sentico_v14_recovery_ready
