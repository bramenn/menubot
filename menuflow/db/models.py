from __future__ import annotations

from typing import Any, Dict, List, Optional
from abc import abstractmethod
import re

from asyncpg import Record
from attr import dataclass
import attr

from mautrix.types import SerializableAttrs, UserID
from mautrix.util.async_db import Database


@dataclass
class Variable(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    value: Any = attr.ib(metadata={"json": "value"})
    pk: int = None
    fk_user: int = None

    @classmethod
    def from_row(cls, row: Record | None) -> User | None:
        if not row:
            return None

        id = row["variable_id"]
        pk = row["pk"]
        value = row["value"]
        fk_user = row["fk_user"]

        if not id:
            return None

        return cls(
            id=id,
            pk=pk,
            value=value,
            fk_user=fk_user,
        )


@dataclass
class User:
    id: int
    user_id: UserID
    context: str
    state: str

    variables: Optional[List[Variable]] = []

    variable_by_id: Dict = {}
    by_phone: Dict = {}
    by_user_id: Dict = {}

    @classmethod
    def from_row(cls, row: Record | None) -> User | None:
        if not row:
            return None

        id = row["id"]
        user_id = row["user_id"]
        context = row["context"]
        state = row["state"]

        if not user_id or not context or not state:
            return None

        cls.add_to_cache

        return cls(
            id=id,
            user_id=user_id,
            context=context,
            state=state,
        )

    @property
    def phone(self):
        user_match = re.match("^@(?P<user_prefix>.+)_(?P<number>[0-9]{8,}):.+$", self.user_id)
        if user_match:
            return user_match.group("number")

    @property
    def add_to_cache(self):

        self.by_user_id[self.user_id] = self

        if self.phone:
            self.by_phone[self.phone] = self

    @abstractmethod
    def get_by_phone(cls, phone) -> "User" | None:
        try:
            return cls.by_phone[phone]
        except KeyError:
            pass

    def get_varibale(self, variable_id: str) -> Variable:
        """If the variable is already in the cache, return it.
        Otherwise, search the list of variables for the variable with the given id,
        and if found, add it to the cache and return it

        Parameters
        ----------
        variable_id : str
            The id of the variable you want to get.

        Returns
        -------
            A variable

        """

        try:
            return self.variable_by_id[variable_id]
        except KeyError:
            pass

        for variable in self.variables:
            if variable_id == variable.id:
                self.set_variable(variable=variable)
                return variable

    def set_variable(self, variable: Variable):
        """It adds a variable to the list of variables

        Parameters
        ----------
        variable : Variable
            The variable to add to the list of variables.

        Returns
        -------
            A list of variables

        """
        if not variable:
            return
        self.variable_by_id[variable.id] = variable.value
        self.variables.append(variable)

    def update_menu(self, context: str):
        """The function updates the state of the bot based on the context of the message

        Parameters
        ----------
        context : str
            The context of the menu. This is the text that the user has entered.

        """
        if not context:
            return

        self.context = context

        if context.startswith("#pipeline"):
            self.state = "VALIDATE_PIPE"

        if context.startswith("#message"):
            self.state = "SHOW_MESSAGE"


class DBManager:
    db: Database

    def __init__(self, db: Database) -> None:
        self.db = db

    ############# User #############
    async def create_user(self, user_id: UserID, context: str, state: str) -> User:
        q = 'INSERT INTO "user" (user_id, context, state) VALUES ($1, $2, $3)'
        return await self.db.execute(q, user_id, context, state)

    async def update_user(self, user_id: UserID, context: str, state: str) -> None:
        q = 'UPDATE "user" SET context = $2, state = $3 WHERE id = $1'
        await self.db.execute(q, user_id, context, state)

    async def get_user_by_user_id(self, user_id: UserID, create: bool = False) -> User:
        q = 'SELECT id, user_id, context, state FROM "user" WHERE user_id=$1'
        row = await self.db.fetchrow(q, user_id)
        if not row and create:
            row = await self.create_user(
                user_id=user_id, context="#message_1", state="SHOW_MESSAGE"
            )

        self.db.log.debug(row)
        return User.from_row(row)

    ############# Variable #############
    async def create_variable(self, user_id, variable_id, value) -> Variable | None:

        variable = await self.get_variable_by_id(variable_id=variable_id)

        if variable:
            return variable

        user = await self.get_user_by_user_id(user_id=user_id, create=True)
        if not user:
            return

        q = "INSERT INTO variable (variable_id, value, fk_user) VALUES ($1, $2, $3)"
        return await self.db.execute(q, variable_id, value, user.id)

    async def update_variable(self, variable_id: str, value: str) -> None:
        q = "UPDATE variable SET value = $2 WHERE id = $1"
        await self.db.execute(q, variable_id, value)

    async def get_variable_by_user(self, user: User) -> User:
        q = "SELECT pk, variable_id, value, fk_user FROM variable WHERE fk_user=$1"
        row = await self.db.fetchrow(q, user.id)

        if not row:
            return

        return Variable.from_row(row)

    async def get_variable_by_id(self, variable_id: str) -> User:
        q = "SELECT pk, variable_id, value, fk_user FROM variable WHERE variable_id=$1"
        row = await self.db.fetchrow(q, variable_id)

        if not row:
            return

        return Variable.from_row(row)
