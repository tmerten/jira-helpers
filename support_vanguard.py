#!/usr/bin/env python3
"""
This script creates Support Vanguard issues for a given Jira Board and Sprint Name
under the epic identified by `vanguard_epic_key`.

Configure this script with the `support_vanguard.yaml` file
(see support_vanguard.example.yaml for an example configuration).

You can also inject environment variables prefixed with JIRA_ for every configuration option.
For example to inject the api_token use JIRA_API_TOKEN as environment variable.
To inject a people_queue use comma separated values in the environment variable:
  export JIRA_PEOPLE_QUEUE=person1.example.com,person2.example.com

TODOs and caveats:

- You need to create the sprints manually first (the python client now seems to support it via JIRA.create_sprint)
  - Note that Jira will pick up your naming scheme if you keep creating sprints, so it's not too hard to prepare them
- The script assumes that a sprint is always two weeks long
- This script is not yet able to detect a new year/when sprints restart with 0
- This does not consider company closing times or holidays
"""

import os
from datetime import datetime, timedelta
import logging
from string import Template
import yaml

from jira import JIRA, JIRAError


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Vanguard:
    """
    This class wraps the support vanguard assignment vor convenience
    """

    # internal representation of the configuration
    _yaml_config = {}

    # errors in the configuration to be reported later
    _config_errors: list[str] = []

    # the jira project key
    project_key: str

    # the board to be scanned for existing issues
    board_id: str

    # the epic under which support vanguard issues should be added
    vanguard_epic_key: str

    # the year of the sprints (used to determine the sprint numbering)
    sprint_template: str

    # the sprint number to start creating issues for (used to determine the sprint numbering)
    sprint_starting_number: int = 18

    # the people
    vanguard_assignee_queue: list[str]

    # the jira client instance
    jira: JIRA

    def __init__(self):
        """
        Load yaml file and try to read config settings
        either from yaml file or environment variables
        and establish connection to Jira
        """

        with open("vanguard.yaml") as stream:
            try:
                self._yaml_config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                exit(1)

        base_url: str = self.read_str_from_yaml_or_environment("base_url")
        self.project_key = self.read_str_from_yaml_or_environment("project_key")
        self.board_id = self.read_str_from_yaml_or_environment("board_id")
        username: str = self.read_str_from_yaml_or_environment("username")
        api_token: str = self.read_str_from_yaml_or_environment("api_token")
        self.vanguard_epic_key = self.read_str_from_yaml_or_environment(
            "vanguard_epic_key"
        )
        self.sprint_template = self.read_str_from_yaml_or_environment("sprint_template")
        self.sprint_starting_number = self.read_int_from_yaml_or_environment(
            "sprint_starting_number"
        )
        self.vanguard_assignee_queue = self.read_list_from_yaml_or_environment(
            "people_queue"
        )

        if len(self._config_errors) > 0:
            print("The following errors have been encountered in the configuration:")
            for error in self._config_errors:
                print(error)
            exit(1)

        # Authenticate with JIRA server and create a client
        logger.debug(f"logging in to Jira as {username}")
        self.jira = JIRA(base_url, basic_auth=(username, api_token))

    def read_from_yaml_or_environment(self, name: str) -> str | list[str] | None:
        """
        Tries to read the variable `name` from the key `name`
        in the YAML file or from an `JIRA_NAME` environment variable.
        """
        value = self._yaml_config.get(name)

        if not value:
            value = os.environ.get(f"JIRA_{name.upper()}")

        if not value:
            error = f"- {name} setting is missing.\n"
            error += f"    Try to add {name} as key to vanguard.yaml or\n"
            error += f"    define a JIRA_{name.upper()} environment variable"
            self._config_errors.append(error)

        return value

    def read_list_from_yaml_or_environment(self, name: str) -> list[str]:
        """
        Tries to convert the value to a list of strings
        """
        raw_value = self.read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            return raw_value.split(",")

        if isinstance(raw_value, list):
            return raw_value

        return []

    def read_str_from_yaml_or_environment(self, name: str) -> str:
        """
        Tries to convert the value to string
        """
        raw_value = self.read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            return raw_value

        return ""

    def read_int_from_yaml_or_environment(self, name: str) -> int:
        """
        Tries to convert the value to string
        """
        raw_value = self.read_from_yaml_or_environment(name)

        if isinstance(raw_value, str):
            try:
                return int(raw_value)
            except ValueError:
                error = f"- {name} is not an integer."
                self._config_errors.append(error)

        return 0

    def sprint_name(self, index: int = 0) -> str:
        """Sprint name from year, starting number and pulse"""
        try:
            return Template(self.sprint_template).substitute(
                sprint_number=self.sprint_starting_number + index
            )
        except KeyError:
            print("Your sprint template needs to contain `${sprint_number}`")
            exit(1)

    def create_and_assign_issue(self, data: dict, email: str, sprint_id: int):
        # to dry run... swap comments below
        logger.info(f"I would create the following issue for {email} and sprint {sprint_id}:")
        logger.info(data)
        # created = self.jira.create_issue(data)
        # self.jira.assign_issue(created.key, email)
        # created.update({
        # 'customfield_10020': sprint_id,  # 10020 is the custom field for sprints
        # })

    def run(self):
        try:
            vanguard_epic = self.jira.issue(self.vanguard_epic_key)
        except JIRAError:
            print(
                f"Vanguard Epic {self.vanguard_epic_key} to create issues under not found."
            )
            exit(2)

        # Get the sprints for the given scrum board
        sprints = list(self.jira.sprints(board_id=self.board_id, state="active,future"))

        vanguards_to_assign = len(self.vanguard_assignee_queue)

        # Check if there are enough sprints for our vanguards to be assigned to
        if len(sprints) < vanguards_to_assign / 2 + 1:
            print(
                f"There are only {len(sprints)} sprints for {vanguards_to_assign} support vanguards."
                f"Please create at least {vanguards_to_assign / 2 + 1 - len(sprints)} sprints first."
            )
            exit(3)

        # check if the first sprint is the current one or a sprint in the future
        # * we do not want to assign vanguards to sprints that ended
        first_sprint_name = self.sprint_name()
        try:
            first_sprint = next(
                sprint for sprint in sprints if sprint.name == first_sprint_name
            )
        except StopIteration:
            print(
                f"Sprint {first_sprint_name} is not a current or future sprint. I cannot continue."
            )
            exit(4)

        # check if there already are support issues for this sprint
        # * we do not want to create duplicates and
        # * we want to make sure that we create an issue for the second sprint week
        #   if one exists for the first week
        support_issues_in_sprint = self.jira.search_issues(
            f'project = "{self.project_key}" AND sprint = {first_sprint.id}'
            " AND parent = {vanguard_epic.key} AND status = Untriaged"
        )

        start_from = 0
        match (len(support_issues_in_sprint)):
            case 0:
                logger.info(
                    "No support vanguard issues found in the first sprint. "
                    "I will crate two support vanguard issues."
                )
            case 1:
                logger.info(
                    "One support vanguard issue found in the first sprint. "
                    "I will create one more support vanguard issue."
                )
                start_from = 1
            case _:
                logger.info(
                    f"Found {len(support_issues_in_sprint)} support vanguard issues.\n"
                    "This should not be the case. Exiting. "
                    f"Are you sure sprint {self.sprint_starting_number} is correct?"
                )
                exit(5)

        for idx, mail in enumerate(self.vanguard_assignee_queue):
            # the sprint number increments every second week (index)
            logger.debug(mail)
            sprint_count = int((idx + start_from) / 2)
            # check if we can find the sprint by name, otherwise we don't want to continue
            sname = self.sprint_name(sprint_count)
            sprint = next(sprint for sprint in sprints if sprint.name == sname)

            if not sprint:
                print(
                    "Sprint with name {sname} not found, please create your sprints first."
                )
                exit(6)

            start_date = datetime.strptime(sprint.startDate, "%Y-%m-%dT%H:%M:%S.%fZ")

            # As the sprint starts on midnight, we need to add one extra day to make sure it's Monday
            # TODO: Bold assumption, also timezone issues?
            if idx % 2 == 1:
                start_date = start_date + timedelta(days=8)
            else:
                start_date = start_date + timedelta(days=1)

            formatted_start_date = start_date.strftime("%Y-%m-%d")

            vanguard_issue_data = {
                "project": {"key": self.project_key},
                "summary": f"Support Vanguard for {sname} week {idx%2 + 1} ({formatted_start_date})",
                "description": (
                    f"Provide support Vanguard for the week from {formatted_start_date}.\n\n"
                    "See https://discourse.maas.io/t/the-support-vanguard/4658 for more details."
                ),
                "issuetype": {
                    "name": "Task"
                },  # Assuming the task type is named as such
                "parent": {"id": vanguard_epic.id},
            }

            # until here we did not create/write anything to Jira
            try:
                self.create_and_assign_issue(
                    vanguard_issue_data, mail, sprint.id
                )
            except JIRAError as e:
                print("An error occurred while creating or updating the issue:", str(e))
                exit(10)


if __name__ == "__main__":
    vanguard = Vanguard()
    vanguard.run()
