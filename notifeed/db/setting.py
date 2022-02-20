#!/usr/bin/env python3

# Imports {{{
# builtins
import logging

# 3rd party
from playhouse.kv import KeyValue

# local modules
from notifeed.constants import DEFAULT_POLL_INTERVAL
from notifeed.db.base import Database

# }}}


log = logging.getLogger(__name__)


class KeyValueStore(KeyValue):
    def create_model(self):
        class KeyValue(Database):
            """
            Settings for Notifeed.
            """

            key = self._key_field
            value = self._value_field

            def __init__(
                self,
                key_field=None,
                value_field=None,
                ordered=False,
                table_name="keyvalue",
            ):
                super().__init__(
                    key_field=key_field,
                    value_field=value_field,
                    ordered=ordered,
                    table_name=table_name,
                )

            class Meta:
                table_name = self._table_name

            @classmethod
            def seed(cls):
                cls.create(name="poll_interval", value=DEFAULT_POLL_INTERVAL * 60)

        return KeyValue


Setting = KeyValueStore(table_name="settings")
