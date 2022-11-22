from typing import Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..user import User
from .node import Node


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Switch(Node):
    """
    ## Switch

    A switch type node allows to validate the content of a jinja variable,
    and from the result to transit to another node.

    content:

    ```
    - id: switch-1
      type: switch
      validation: '{{ opt }}'
      cases:
      - id: 1
        o_connection: m1
      - id: 2
        o_connection: m2
      - id: default
        o_connection: m3
    ```
    """

    validation: str = ib(default=None, metadata={"json": "validation"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    async def load_cases(self, user: User = None):
        """It loads the cases into a dictionary.

        Parameters
        ----------
        user : User
            User = None

        Returns
        -------
            A dictionary of cases.

        """

        cases_dict = {}

        for case in self.cases:
            cases_dict[str(case.id)] = case.o_connection
            if case.variables and user:
                for varible in case.variables:
                    try:
                        await user.set_variable(
                            variable_id=varible,
                            value=case.variables[varible],
                        )
                    except Exception as e:
                        self.log.warning(e)
                        continue

        return cases_dict

    async def run(self, user: User) -> str:
        """It takes a dictionary of variables, runs the rule,
        and returns the connection that matches the case

        Parameters
        ----------
        variables : dict
            dict

        Returns
        -------
            The str object

        """

        self.log.debug(f"Executing validation of input {self.id} for user {user.user_id}")

        res = None

        try:
            res = self.validation
            # TODO What would be the best way to handle this, taking jinja into account?
            # if res == "True":
            #     res = True

            # if res == "False":
            #     res = False

        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            res = "except"

        return await self.get_case_by_id(res, user=user)

    async def get_case_by_id(self, id: str, user: User = None) -> str:
        try:
            cases = await self.load_cases(user=user)
            case_result = cases[id]
            self.log.debug(f"The case {case_result} has been obtained in the input node {self.id}")
            return case_result
        except KeyError:
            self.log.debug(f"Case not found {id} the default case will be sought")
            return cases["default"]
