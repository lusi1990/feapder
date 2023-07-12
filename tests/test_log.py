# -*- coding: utf-8 -*-
"""
Created on 2021/6/18 10:36 上午
---------
@summary:
---------
@author: Boris
@email: boris_liu@foxmail.com
"""
import json
import sys

from loguru import logger

from feapder.utils.log import log


def sink_serializer(message):
    record = message.record
    simplified = {
        "level": record["level"].name,
        "message": record["message"],
        "timestamp": record["time"].isoformat(),
        'thread': record['thread'].name,
        'name': record['name'],
        'filename': record['file'].name,
        'function': record['function'],
        'line': record['line']
    }
    serialized = json.dumps(simplified)
    print(serialized, file=sys.stderr)


def test():
    logger.add(sink_serializer, level="INFO", format='{level}: {time} {thread} [{name}] {message}')
    logger.info("123")
    logger.debug("123")
    logger.warning("123")


if __name__ == '__main__':
    log.debug("debug")
    log.info("info")
    log.success("success")
    log.warning("warning")
    log.error("error")
    log.critical("critical")
    log.exception("exception")

    # test()
