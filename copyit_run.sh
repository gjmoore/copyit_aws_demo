#!/usr/bin/env bash

#
# Dockerfile ENTRYPOINT script
#
# The following environment variables are assumed:
# SRC_OBJECT
# DEST_OBJECT
#

copyit --src ${SRC_OBJECT} --dest ${DEST_OBJECT} --log INFO

