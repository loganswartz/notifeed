#!/usr/bin/env python3

# Imports {{{
# builtins
from collections import defaultdict
from importlib import import_module
import inspect
import pathlib
import re
import textwrap
from traceback import format_exception
from typing import (
    Callable,
    Iterable,
    Dict,
    List,
    Type,
    TypeVar,
)

# 3rd party
from bs4 import BeautifulSoup

# }}}


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


Item = TypeVar("Item")
Result = TypeVar("Result")


def partition(
    items: Iterable[Item], test: Callable[[Item], Result]
) -> Dict[Result, List[Item]]:
    partitions: Dict[Result, List[Item]] = defaultdict(list)

    for item in items:
        partitions[test(item)].append(item)

    return partitions


def get_traceback(exception: Exception):
    msg = format_exception(type(exception), exception, exception.__traceback__)
    return ''.join(msg).strip()
