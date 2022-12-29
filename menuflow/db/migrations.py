from asyncpg import Connection
from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Initial revision")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute(
        """CREATE TABLE "room" (
            id          SERIAL PRIMARY KEY,
            room_id     TEXT NOT NULL,
            variables   JSON,
            node_id     TEXT,
            state       TEXT
        )"""
    )
    await conn.execute(
        """CREATE TABLE "user" (
            id          SERIAL PRIMARY KEY,
            mxid        TEXT NOT NULL,
        )"""
    )
    await conn.execute(
        """CREATE TABLE client (
            id           TEXT    PRIMARY KEY,
            homeserver   TEXT    NOT NULL,
            access_token TEXT    NOT NULL,
            device_id    TEXT    NOT NULL,

            next_batch TEXT NOT NULL,
            filter_id  TEXT NOT NULL,

            autojoin BOOLEAN NOT NULL
        )"""
    )
