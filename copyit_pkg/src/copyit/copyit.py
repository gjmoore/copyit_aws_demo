#!/usr/bin/env python

import argparse
import boto3
import logging
from urllib.parse import urlparse

logging.basicConfig()
log = logging.getLogger(__name__)


def copyit( src, dest):
    """Copy AWS S3 src object to AWS S3 dest object. src and dest buckets are
    assumed to exist.

    """
    s3 = boto3.client('s3')
    parsed_src_url = urlparse(src)
    parsed_dest_url = urlparse(dest)

    log.info('copying %s to %s...', src, dest)
    s3.copy(
        # from:
        {'Bucket': parsed_src_url.netloc,
        'Key': parsed_src_url.path.lstrip('/')},
        # to:
        parsed_dest_url.netloc,
        parsed_dest_url.path.lstrip('/'))
    log.info('...done')

    # in practice, above could be replaced with:
    # s3.get_object()
    # do_interesting_science()
    # s3.put_object()


def main():
    """Command-line entry point.

    """
    parser = argparse.ArgumentParser(
        description="""
	    Copy AWS S3 objects (Simple Python test implementation of 'aws s3 cp')""",
        epilog="""
        src and dest buckets are assumed to exist.""")
    parser.add_argument('--src', help="""
        AWS S3 url of source object.""")
    parser.add_argument('--dest', help="""
        AWS S3 url of destination object.""")
    parser.add_argument('--log', dest='log_level',
        choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'],
        default='WARNING', help="""
        Set logging level (default: %(default)s)""")
    args = parser.parse_args()

    log.setLevel(args.log_level)

    copyit( args.src, args.dest)


if __name__=='__main__':
    main()

