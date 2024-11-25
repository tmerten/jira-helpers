"""
This class can be derived to create issues for a given Jira Board and Sprint Name
under the epic identified by `epic_key`.

Configure this script with the `yaml` file passed into its constructor.
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

from abc import ABC, abstractmethod
import math

from datetime import datetime, timedelta
import logging
from string import Template

from jira import JIRAError

from .jira_connector import JiraConnector

logger = logging.getLogger("jira_helpers")

class CreateAndAssignTasks(JiraConnector, ABC):
    """
    This class wraps the support vanguard assignment vor convenience
    """

    # the jira project key
    project_key: str

    # the board to be scanned for existing issues
    board_id: str

    # the epic under which support vanguard issues should be added
    epic_key: str

    # the year of the sprints (used to determine the sprint numbering)
    sprint_template: str

    # the sprint number to start creating issues for (used to determine the sprint numbering)
    sprint_starting_number: int

    # the people
    assignee_queue: list[str]

    # do not make any changes
    dry_run: bool

    def __init__(self, config_file):
        """Inject correct support file in super class"""
        super(CreateAndAssignTasks, self).__init__(config_file)

    def configure(self):
        """Vanguard specific configuration options"""
        self.project_key = self._read_str_from_yaml_or_environment("project_key")
        self.board_id = self._read_str_from_yaml_or_environment("board_id")
        self.epic_key = self._read_str_from_yaml_or_environment("epic_key")
        self.sprint_template = self._read_str_from_yaml_or_environment(
            "sprint_template"
        )
        self.sprint_starting_number = self._read_int_from_yaml_or_environment(
            "sprint_starting_number"
        )
        self.assignee_queue = self._read_list_from_yaml_or_environment("people_queue")
        self.dry_run = self._read_bool_from_yaml_or_environment("dry_run")

    def sprint_name(self, index: int = 0) -> str:
        """Sprint name from year, starting number and pulse"""
        try:
            template = Template(self.sprint_template).substitute(
                sprint_number=self.sprint_starting_number + index
            )
            logger.debug(f"Sprint template compiled to: {template}")
            return template
        except KeyError:
            print("Your sprint template needs to contain `${sprint_number}`")
            exit(1)

    def create_and_assign_issue(self, data: dict, email: str, sprint_id: int):
        if self.dry_run:
            logger.info(
                f"I would create the following issue for {email} and sprint {sprint_id}:"
            )
            logger.info(data)
        else:
            created = self.jira.create_issue(data)
            self.jira.assign_issue(created.key, email)
            created.update({
            'customfield_10020': sprint_id,  # 10020 is the custom field for sprints
            })
            logger.debug(
                f"created issue for {email} and sprint {sprint_id}:"
            )
            logger.debug(data)

    @abstractmethod
    def issue_data(self, epic, sname, idx, formatted_start_date):
        """
        Needs to returns an object in the form of
        {
            "project": {
                "key": "JIRA_PROJECT"
            },
            "summary": "issue summary"
            "description": (
                "Issue description, can be multi-line with \n"
            ),
            "issuetype": {
                "name": "Task"
            },  # Assuming the task type is named as such
            "parent": {
                "id": epic_to_nest_this_under.id
            },
        }
        """
        return {}

    def run(self):
        try:
            vanguard_epic = self.jira.issue(self.epic_key)
        except JIRAError:
            print(f"Vanguard Epic {self.epic_key} to create issues under not found.")
            exit(2)

        # Get the sprints for the given scrum board
        sprints = list(self.jira.sprints(board_id=self.board_id, state="active,future"))

        vanguards_to_assign = len(self.assignee_queue)

        # Check if there are enough sprints for our vanguards to be assigned to
        if len(sprints) < vanguards_to_assign / 2 + 1:
            print(
                f"There are only {len(sprints)} sprints for {vanguards_to_assign} support vanguards.\n"
                f"Please create at least {math.ceil(vanguards_to_assign / 2) + 1 - len(sprints)} sprints first or assign no more than { vanguards_to_assign - len(sprints * 2) } vanguards."
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
            f' AND parent = {vanguard_epic.key} AND status = Untriaged'
        )

        start_from = 0
        match (len(support_issues_in_sprint)):
            case 0:
                logger.info(
                    f"No support vanguard issues found in sprint {first_sprint}. "
                    "I will crate two support vanguard issues."
                )
            case 1:
                logger.info(
                    f"No support vanguard issue found in sprint {first_sprint}. "
                    "I will create one more issue for the second week."
                )
                start_from = 1
            case _:
                logger.info(
                    f"Found {len(support_issues_in_sprint)} support vanguard issues.\n"
                    "This should not be the case. Exiting. "
                    f"Are you sure sprint {self.sprint_starting_number} is correct?"
                )
                exit(5)

        for idx, mail in enumerate(self.assignee_queue, start_from):
            # the sprint number increments every second week (index)
            logger.debug(mail)
            sprint_count = int((idx) / 2)
            # check if we can find the sprint by name, otherwise we don't want to continue
            sname = self.sprint_name(sprint_count)

            try:
                sprint = next(sprint for sprint in sprints if sprint.name == sname)
            except StopIteration:
                print(
                    f"Sprint with name {sname} not found, please create your sprints first."
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

            issue_data = self.issue_data(
                vanguard_epic, sname, idx, formatted_start_date
            )

            # until here we did not create/write anything to Jira
            try:
                self.create_and_assign_issue(issue_data, mail, sprint.id)
            except JIRAError as e:
                print("An error occurred while creating or updating the issue:", str(e))
                exit(10)
