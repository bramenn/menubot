from __future__ import annotations

from typing import Dict, List, Tuple

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ContentTypeError
from attr import dataclass, ib
from jinja2 import Template
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..room import RoomState
from .switch import Case, Switch


@dataclass
class HTTPRequest(Switch):
    """
    ## HTTPRequest

    HTTPRequest is a subclass of Switch which allows sending a message formatted with jinja
    variables and capturing the response to transit to another node according to the validation

    content:

    ```
    - id: 'r1'
      type: 'http_request'
      method: 'GET'
      url: 'https://inshorts.deta.dev/news?category={{category}}'

      variables:
        news: data

      cases:
        - id: 200
          o_connection: m1
        - id: default
          o_connection: m2
    ```
    """

    method: str = ib(default=None, metadata={"json": "method"})
    url: str = ib(default=None, metadata={"json": "url"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    cookies: Dict = ib(metadata={"json": "cookies"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "query_params"}, factory=dict)
    headers: Dict = ib(metadata={"json": "headers"}, factory=dict)
    basic_auth: Dict = ib(metadata={"json": "basic_auth"}, factory=dict)
    data: Dict = ib(metadata={"json": "data"}, factory=dict)
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    @property
    def _url(self) -> Template:
        return self.render_data(self.url)

    @property
    def _variables(self) -> Template:
        return self.render_data(self.serialize()["variables"])

    @property
    def _cookies(self) -> Template:
        return self.render_data(self.serialize()["cookies"])

    @property
    def _headers(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["headers"])

    @property
    def _auth(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["basic_auth"])

    @property
    def _query_params(self) -> Dict:
        return self.render_data(self.serialize()["query_params"])

    @property
    def _data(self) -> Dict:
        return self.render_data(self.serialize()["data"])

    async def request(self, session: ClientSession) -> Tuple(int, str):

        request_body = {}

        if self.query_params:
            request_body["params"] = self._query_params

        if self.basic_auth:
            request_body["auth"] = BasicAuth(
                login=self._auth["login"],
                password=self._auth["password"],
            )

        if self.headers:
            request_body["headers"] = self._headers

        if self.data:
            request_body["json"] = self._data

        response = await session.request(self.method, self._url, **request_body)

        variables = {}
        o_connection = None

        if self._cookies:
            for cookie in self._cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"node: {self.id} method: {self.method} url: {self._url} status: {response.status}"
        )

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = {}

        if isinstance(response_data, dict):
            # Tulir and its magic since time immemorial
            serialized_data = RecursiveDict(CommentedMap(**response_data))
            if self._variables:
                for variable in self._variables:
                    try:
                        variables[variable] = self.render_data(
                            serialized_data[self.variables[variable]]
                        )
                    except KeyError:
                        pass
        elif isinstance(response_data, str):
            if self._variables:
                for variable in self._variables:
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass

                    break

        if self.cases:
            o_connection = await self.get_case_by_id(id=str(response.status))

        if o_connection:
            await self.room.update_menu(
                node_id=o_connection, state=RoomState.END if not self.cases else None
            )

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, await response.text()
