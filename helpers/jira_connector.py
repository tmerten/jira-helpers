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
import argparse
import logging
import yaml

from jira import JIRA

from helpers.actions import EnvDefault, RequiredOrDefault


logger = logging.getLogger('jira_helpers')

class JiraConnector(ABC):
    """
    Abstract class that handles connection to Jira and
    reading the configuration to derive from.

    It provides an instance of JIRA as self.jira and
    initializes all configuration variables.
    """

    # internal representation of the configuration
    _yaml_config:dict = {}

    _config_file: str

    parser: argparse.ArgumentParser

    args: argparse.Namespace

    # the jira client instance
    jira: JIRA


    def __init__(self, config_file):
        """
        Load yaml file and try to read config settings
        either from yaml file or environment variables
        and establish connection to Jira
        """
        self.config_file = config_file
        self.parser = argparse.ArgumentParser(
            prog='Jira Helper'
        )

        # add default values from config files
        logger.debug(f'trying to load defaults from {self.config_file}')
        with open(self.config_file) as stream:
            try:
                self._yaml_config = yaml.safe_load(stream)
                self.parser.set_defaults(**self._yaml_config)
            except yaml.YAMLError as exc:
                print(exc)
                exit(1)

        self.parser.add_argument('-b', '--base-url', required=True, action=RequiredOrDefault,
            help='The URL of your Jira instance.')
        self.parser.add_argument('-u', '--username', required=True, action=RequiredOrDefault,
            help='The username to login to Jira.')
        self.parser.add_argument('-t', '--api-token', required=True, action=EnvDefault, envvar='JIRA_API_TOKEN',
            help='The jira API token, can also be specified as JIRA_URL environment variable.')
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument('-dry', '--dry-run', dest='dry_run', action='store_true',
            help='Do not actually change anything, perform a dry run.')
        group.add_argument('-no-dry', '--no-dry-run', dest='dry_run', action='store_false',
            help='Overwrite a dry run setting from config file.')
        self.parser.add_argument('-v', '--verbose', action='store_true',
            help='Show debug logging output.', )

        # let sub-classes inject their own parameters
        self.configure()

        with open(self.config_file) as stream:
            try:
                self._yaml_config = yaml.safe_load(stream)
                self.parser.set_defaults(**self._yaml_config)
            except yaml.YAMLError as exc:
                print(exc)
                exit(1)

        # update args from command line and environment variables
        # overrides config file defaults above
        self.args = self.parser.parse_args()

        if self.args.verbose:
            logger.setLevel(logging.DEBUG)

        base_url: str = self.args.base_url
        username: str = self.args.username
        api_token: str = self.args.api_token

        # Authenticate with JIRA server and create a client
        logger.debug(f'logging in to Jira at {base_url} as {username}')
        self.jira = JIRA(base_url, basic_auth=(username, api_token))

    @abstractmethod
    def configure(self):
        """
        Overwrite this method to inject additional configuration options
        """
        # Your implementation will look something like this
        # self.parser.add_argument('-a', '--argument',
        #    help='The argument I want to add in my subclass')
        pass
