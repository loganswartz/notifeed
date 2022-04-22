#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
import inspect
import logging
import pathlib
import re
import sys
import textwrap
from collections import defaultdict
from importlib import import_module
from traceback import format_exception
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Sized,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from urllib.parse import urlparse

# 3rd party
from bs4 import BeautifulSoup
from faker import Faker

# local modules
from notifeed.constants import BROTLI_SUPPORTED

# }}}


log = logging.getLogger(__name__)
faker = Faker()


def strip_html(string: str):
    """
    Use BeautifulSoup to strip out any HTML tags from strings.
    """
    return BeautifulSoup(string, "html.parser").get_text()


def condense(text: str) -> str:
    """
    Strip out all HTML from the text and collapse all extraneous whitespace.
    """
    paragraphs = [
        re.sub(r"\s+", " ", part).strip() for part in text.split("\n\n") if part.strip()
    ]
    filled = (textwrap.fill(paragraph) for paragraph in paragraphs)
    return "\n\n".join(filled)


def list_items(items: Iterable, found_msg: str, not_found_msg: str, line_fmt: str):
    if not items:
        log.info(not_found_msg)
        sys.exit(0)

    log.info(found_msg)
    for item in items:
        log.info(line_fmt.format(**item.__data__))


class Reporter(object):
    def __init__(self, success: str, failure: str, pre: Optional[str] = None):
        self.pre = pre
        self.success = success
        self.failure = failure

    def __enter__(self):
        if self.pre is not None:
            log.info(self.pre)

    def __exit__(self, exception_cls, exception, traceback):
        if exception is None:
            log.info(self.success)
        else:
            log.error(self.failure.format(exception=exception))
            return True  # suppress traceback


def get_traceback(exception: Exception):
    msg = format_exception(type(exception), exception, exception.__traceback__)
    return "".join(msg).strip()


def generate_headers(url):
    """
    A set of headers needed by some sites to actually respond correctly.

    Typically needed to avoid being stopped by anti-scraping measures.
    """
    headers = {
        "User-Agent": faker.user_agent(),
        "Upgrade-Insecure-Requests": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate" + ", br" if BROTLI_SUPPORTED else "",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "http://www.google.com/",
        "Host": urlparse(url).hostname,
    }
    return headers


T = TypeVar("T", bound=Type)


def import_subclasses(
    cls: T, __package__: str, path: pathlib.Path, recursive=True, blacklist=[]
) -> Dict[str, T]:
    def relative_to_package(package: pathlib.Path, path: pathlib.Path):
        relative = path.relative_to(package).with_suffix("")
        return str(relative).replace("/", ".")

    def is_subclass(checking: type, parent: type):
        return (
            inspect.isclass(checking)
            and issubclass(checking, parent)
            and checking is not parent
        )

    blacklist = ["<stdin>", "__init__.py", "__main__.py", "base.py", *blacklist]

    find = path.rglob if recursive else path.glob
    files = [
        file for file in find("*.py") if file.is_file() and file.name not in blacklist
    ]

    modules = {
        module.stem: import_module(
            ".".join([__package__, relative_to_package(path, module)])
        )
        for module in files
    }

    return {
        name: obj
        for module in modules.values()
        for name, obj in module.__dict__.items()
        if is_subclass(obj, cls)
    }


T = TypeVar("T")


class Boolable(Protocol):
    def __bool__(self) -> bool:
        ...


BoolLike = Union[Sized, Boolable, str, int, list, tuple, bool, None]


def find(lst: List[T], test: Callable[[T], BoolLike]) -> Optional[int]:
    return next((idx for idx, item in enumerate(lst) if test(item)), None)


Item = TypeVar("Item")
Result = TypeVar("Result")


def partition(
    items: Iterable[Item], test: Callable[[Item], Result]
) -> Dict[Result, List[Item]]:
    partitions: Dict[Result, List[Item]] = defaultdict(list)

    for item in items:
        partitions[test(item)].append(item)

    return partitions


K = TypeVar("K")
V = TypeVar("V")
TaskResult = TypeVar("TaskResult")
TaskKey = TypeVar("TaskKey")
ResultList = List[Tuple[K, V]]


async def pool(
    *tasks: Coroutine[Any, Any, TaskResult], keys: Iterable[TaskKey]
) -> Tuple[ResultList[TaskKey, TaskResult], ResultList[TaskKey, Exception]]:
    """
    Pool and execute a list of tasks.

    Returns a tuple containing a list of completed results and a list of exceptions that occurred.
    """
    results = await asyncio.gather(*tasks, return_exceptions=True)

    partitioned = partition(
        zip(keys, results), lambda item: isinstance(item[1], Exception)
    )
    exceptions = partitioned.get(True, [])
    updates = partitioned.get(False, [])

    return (updates, exceptions)
