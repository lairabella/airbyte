#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pendulum
from pendulum import DateTime

import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream


class OpenExchangeRates(HttpStream, ABC):
    url_base = "https://openexchangerates.org/api/"

    primary_key = None
    cursor_field = "timestamp"


    def __init__(self, base: Optional[str], start_date: str, app_id: str) -> None:
        super().__init__()

        self.base = base
        self.start_date = start_date
        self.app_id = app_id
        self._cursor_value = None

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:

        params = {}

        if self.base is not None:
            params["base"] = self.base

        return params

    def request_headers(self, **kwargs) -> MutableMapping[str, Any]:
        headers = {"Authorization": f"Token {self.app_id}", "Content-Type": "application/json"}

        return headers

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        response_json = response.json()
        yield response_json

    def stream_slices(self, stream_state: Mapping[str, Any] = None, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        stream_state = stream_state or {}
        start_date = pendulum.parse(stream_state.get(self.date_field_name, self.start_date))
        return self._chunk_date_range(start_date)

    def path(
        self,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None
    ) -> str:
        return f"historical/{stream_slice[self.date_field_name]}.json"


    def _chunk_date_range(self, start_date: DateTime) -> List[Mapping[str, Any]]:
        """
        Returns a list of each day between the start date and now.
        The return value is a list of dicts {'date': date_string}.
        """
        dates = []
        while start_date < pendulum.now():
            dates.append({"timestamp": start_date.to_date_string()})
            start_date = start_date.add(days=1)
        return dates


# Source
class SourceOpenExchangeRates(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        Checks the connection by sending a request to /usage and checks the remaining quota

        :param config:  the user-input config object conforming to the connector's spec.yaml
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API successfully, (False, error) otherwise.
        """
        try:
            headers = {"Authorization": f"Token {config['app_id']}"}

            resp = requests.get(f"{OpenExchangeRates.url_base}usage.json", headers=headers)
            status = resp.status_code

            logger.info(f"Ping response code: {status}")
            response_dict = resp.json()

            if status == 200:
                quota_remaining = response_dict["data"]["usage"]["requests_remaining"]

                if quota_remaining > 0:
                    return True, None

                return False, "Quota exceeded"
            else:
                description = response_dict.get("description")
                return False, description
        except Exception as e:
            return False, e

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """
        return [OpenExchangeRates(base=config['base'], start_date=config['start_date'], app_id=config['app_id'])]
