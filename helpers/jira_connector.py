"""
This is a base class that other helpers can be derived from.
It handles the jira connection and provides an abstract run method

Configure this script with the a yaml` file
(see e.g. support_vanguard.example.yaml for an example configuration).

You can also inject environment variables prefixed with JIRA_ for every configuration option.
For example to inject the api_token use JIRA_API_TOKEN as environment variable.
To inject a people_queue use comma separated values in the environment variable:
  export JIRA_PEOPLE_QUEUE=person1.example.com,person2.example.com
"""

from abc import ABC, abstractmethod
import os
from datetime import datetime, timedelta
import logging
from string import Template
import yaml

from jira import JIRA, JIRAError

logger = logging.getLogger("jira_helpers")

class JiraConnector(ABC):
    """
    Abstract class that handles connection to Jira and
    reading the configuration to derive from.

    It provides an instance of JIRA as self.jira and
    initializes all configuration variables.
    """

    # internal representation of the configuration
    _yaml_config = {}

    # errors in the configuration to be reported later
    _config_errors: list[str] = []

    _config_file: str

    # the jira client instance
    jira: JIRA


    def __init__(self, config_file):
        """
        Load yaml file and try to read config settings
        either from yaml file or environment variables
        and establish connection to Jira
        """
        self.config_file = config_file

        with open(self.config_file) as stream:
            try:
                self._yaml_config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                exit(1)

        base_url: str = self._read_str_from_yaml_or_environment("base_url")
        username: str = self._read_str_from_yaml_or_environment("username")
        api_token: str = self._read_str_from_yaml_or_environment("api_token")

        self.configure()

        if len(self._config_errors) > 0:
            print("The following errors have been encountered in the configuration:")
            for error in self._config_errors:
                print(error)
            exit(1)

        # Authenticate with JIRA server and create a client
        logger.debug(f"logging in to Jira as {username}")
        self.jira = JIRA(base_url, basic_auth=(username, api_token))

    @abstractmethod
    def configure(self):
        """
        Overwrite this method to inject additional configuration options
        """
        # Your implementation will look something like this
        #  self.sprint_template = self.read_str_from_yaml_or_environment("sprint_template")
        #  self.number = self.read_int_from_yaml_or_environment("a_number")
        #  self.people = self.read_list_from_yaml_or_environment("people_queue")
        pass

    def _read_from_yaml_or_environment(self, name: str) -> str | list[str] | None:
        """
        Tries to read the variable `name` from the key `name`
        in the YAML file or from an `JIRA_NAME` environment variable.
        """
        value = self._yaml_config.get(name)

        if not value:
            value = os.environ.get(f"JIRA_{name.upper()}")

        if not value:
            error = f"- {name} setting is missing.\n"
            error += f"    Try to add {name} as key to {self.config_file} or\n"
            error += f"    define a JIRA_{name.upper()} environment variable"
            self._config_errors.append(error)

        return value

    def _read_list_from_yaml_or_environment(self, name: str) -> list[str]:
        """
        Tries to convert the value to a list of strings
        """
        raw_value = self._read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            return raw_value.split(",")

        if isinstance(raw_value, list):
            return raw_value

        return []

    def _read_str_from_yaml_or_environment(self, name: str) -> str:
        """
        Tries to convert the value to string
        """
        raw_value = self._read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            return raw_value

        return ""

    def _read_int_from_yaml_or_environment(self, name: str) -> int:
        """
        Tries to convert the value to int
        """
        raw_value = self._read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            try:
                return int(raw_value)
            except ValueError:
                error = f"- {name} is not an integer."
                self._config_errors.append(error)

        return 0

    def _read_bool_from_yaml_or_environment(self, name: str) -> bool:
        """
        Tries to convert the value to boolean
        """
        raw_value = self._read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            return raw_value.lower() in ['true', '1', 't', 'y', 'yes']
        else:
            # in case it is None we assume it is falsy
            return False
