#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from typing import List, Protocol, Type, Union

# 3rd party
from peewee import DatabaseProxy, Model, make_snake_case

# }}}


log = logging.getLogger(__name__)


def create_table_name(model):
    snake = make_snake_case(model.__name__)
    pluralized = snake + "s"
    return pluralized


db_proxy = DatabaseProxy()


class Database(Model):
    class Meta:
        database = db_proxy
        table_function = create_table_name

    @classmethod
    def seed(cls):
        subclasses = cls.__subclasses__()
        nonexistent = [subcls for subcls in subclasses if not subcls.table_exists()]

        if cls._meta and cls._meta.database:
            cls._meta.database.create_tables(nonexistent)

        for subcls in nonexistent:
            if hasattr(subcls, "seed"):
                subcls.seed()

    def keys(self):
        return self.__data__.keys()

    def __getitem__(self, key):
        return self.__data__[key]
