#!/bin/bash

set -e
cd "$(dirname "$0")"

run_script ext/run_script_ssh.py \
    --host ${PRINTER_3D_HOST} \
    --user ${PRINTER_3D_USER} \
    --pwd ${PRINTER_3D_PWD} \
    _run_pronsole_device.sh
