#!/usr/bin/env bash

# set up some copyit test data on s3:

aws s3 mb s3://copyit
aws s3 sync ./data/source s3://copyit/source

