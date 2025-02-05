#!/usr/bin/env python3
"""
Collect modules and python stubs from other projects and stores them in the all_stubs folder
The all_stubs folder should be mapped/symlinked to the micropython_stubs/stubs repo/folder

"""
# pylint: disable= line-too-long, W1202
# Copyright (c) 2020 Jos Verlinde
# MIT license
# pylint: disable= line-too-long
import logging
import utils
import sys

log = logging.getLogger(__name__)

if __name__ == "__main__":
    # generate typeshed files for all scripts

    if len(sys.argv) == 1:
        # no params
        stub_path = utils.STUB_FOLDER
    elif len(sys.argv) == 2:
        stub_path = sys.argv[1]
    log.info("Generate type hint files (pyi) in folder: {}".format(stub_path))
    utils.make_stub_files(stub_path, levels=7)