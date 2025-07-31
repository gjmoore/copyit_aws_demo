#!/usr/bin/env bash

set -x 

JOB_QUEUE=copyit-job-queue
JOB_DEFINITION=copyit-job-definition

SRC=s3://copyit/source/
DEST=s3://copyit/dest/

# use AWS Batch to copy all files in $SRC to $DEST:

for file in $(aws s3 ls ${SRC} | awk '{print $4}'); do

    aws batch submit-job \
        --job-name          ${file%.*} \
        --job-queue         $JOB_QUEUE \
        --job-definition    $JOB_DEFINITION \
        --container-overrides "{\"environment\": [{\"name\": \"SRC_OBJECT\", \"value\": \"$SRC$file\"}, {\"name\": \"DEST_OBJECT\", \"value\": \"$DEST$file\"}] }"

done
