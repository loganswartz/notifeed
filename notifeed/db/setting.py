#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from typing import Any

# 3rd party
from peewee import CharField, Model, PostgresqlDatabase, SqliteDatabase
from playhouse.fields import PickleField
from playhouse.kv import KeyValue
from playhouse.sqlite_ext import SqliteExtDatabase

# local modules
from notifeed.constants import DEFAULT_SETTINGS
from notifeed.db.base import db_proxy

# }}}


log = logging.getLogger(__name__)


class KeyValueStore(KeyValue):
    """
    A modified version of the KV store that supports using a DB proxy.

    Usage:
        Setting = KeyValueStore(database=proxy)

        # before using
        Setting.create_table()  # or Setting.seed()

        # you can now use normally
        Setting['poll_interval'] = 15*60
    """

    def __init__(
        self,
        key_field=None,
        value_field=None,
        ordered=False,
        database=None,
        table_name="keyvalue",
    ):
        if key_field is None:
            key_field = CharField(max_length=255, primary_key=True)
        if not key_field.primary_key:
            raise ValueError("key_field must have primary_key=True.")

        if value_field is None:
            value_field = PickleField()

        self._key_field = key_field
        self._value_field = value_field
        self._ordered = ordered
        self._database = database or SqliteExtDatabase(":memory:")
        self._table_name = table_name
        support_on_conflict = isinstance(self._database, PostgresqlDatabase) or (
            isinstance(self._database, SqliteDatabase)
            and self._database.server_version >= (3, 24)
        )
        if support_on_conflict:
            self.upsert = self._postgres_upsert
            self.update = self._postgres_update
        else:
            self.upsert = self._upsert
            self.update = self._update

        self.model = self.create_model()
        self.key = self.model.key
        self.value = self.model.value

    def create_model(self):
        class KeyValue(Model):
            """
            Settings for Notifeed.
            """

            key = self._key_field
            value = self._value_field

            class Meta:
                database = self._database
                table_name = self._table_name

            @classmethod
            def seed(cls):
                cls.create_table()

        return KeyValue

    def __getitem__(self, expr) -> Any:
        try:
            return super().__getitem__(expr)
        except KeyError:
            if expr not in DEFAULT_SETTINGS:
                raise

            return DEFAULT_SETTINGS[expr]

    def get(self, key, default=None) -> Any:
        return super().get(key, default)


Setting = KeyValueStore(database=db_proxy, table_name="settings")
