"""
This class can be derived with concrete implementations.

It can be used to create to create issues to plan recurring tasks
that are to be rotated in a team (such as support vanguard or team presentations).
It does this for a given Jira Board and Sprint name under the epic identified by `epic_key`.

Configure this script with the `yaml` file passed into its constructor
and or the options given to argparse in the `configuration` method
(see support_vanguard.example.yaml for an example configuration).

- You need to create the sprints manually first (the python client now seems to support it via JIRA.create_sprint)
  - Note that Jira will pick up your naming scheme if you keep creating sprints, so it's not too hard to prepare them
- The script assumes that a sprint is always two weeks long
- This script is not yet able to detect a new year/when sprints restart with 0
- This does not consider company closing times or holidays
"""

from abc import ABC, abstractmethod
import sys

from datetime import datetime, timedelta
import logging
from string import Template

from jira import Issue, JIRAError
from jira.client import ResultList
from jira.resources import Sprint

from .jira_connector import JiraConnector

logger = logging.getLogger('jira_helpers')

class CreateAndAssignTasks(JiraConnector, ABC):

    epic: Issue

    """
    This class wraps the creating and assigning issues to a people queue
    """
    def __init__(self, config_file):
        """Inject correct configuration file in super class"""
        super(CreateAndAssignTasks, self).__init__(config_file)

    def configure(self):
        """Vanguard specific configuration options"""
        self.parser.add_argument('-p', '--project',
            help='The Jira project key.')
        self.parser.add_argument('-B', '--board',
            help='The Jira board to be scanned for existing issues.')
        self.parser.add_argument('-e', '--epic',
            help='The epic under which the issues should be added.')
        self.parser.add_argument('--sprint-template',
            help='The sprint template. It is highly recommended to configure this in the config file.')
        self.parser.add_argument('-a', '--assignee', nargs='+',
            help='The list of assignees. It is highly recommended to configure this in the config file.')

    def sprint_name(self, index: int = 0) -> str:
        """Sprint name from year, starting number and pulse"""
        try:
            template = Template(self.args.sprint_template).substitute(
                sprint_number=f'{self.args.sprint_starting_number + index:02d}'
            )
            logger.debug(f'Sprint template compiled to: {template}')
            return template
        except KeyError:
            sys.stderr.write('Your sprint template needs to contain `${sprint_number}`')
            exit(1)

    def assign_issue(self, data: dict, email: str, sprint_id: int):
        if self.args.dry_run:
            print(
                f'I would create the following issue for {email} and sprint {sprint_id}:'
            )
            print(data)
        else:
            created = self.jira.create_issue(data)
            self.jira.assign_issue(created.key, email)
            created.update({
            'customfield_10020': sprint_id,  # 10020 is the custom field for sprints
            })
            logger.debug(
                f'created issue for {email} and sprint {sprint_id}:'
            )
            logger.debug(data)

    @abstractmethod
    def issue_data(self, sname, week, formatted_start_date):
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

    def prepare_and_assign_issue(self, sprint, assignee_email, week):
        start_date = datetime.strptime(sprint.startDate, '%Y-%m-%dT%H:%M:%S.%fZ')
        days = 1 if week == 1 else 8

        issue_data = self.issue_data(
            sprint.name,
            week,
            (start_date + timedelta(days=days)).strftime('%Y-%m-%d')
        )
        self.assign_issue(
            issue_data,
            assignee_email,
            sprint.id
        )

    def run(self):
        try:
            self.epic = self.jira.issue(self.args.epic)
        except JIRAError:
            sys.stderr.write(f"Epic {self.args.epic} to create child issues not found.")
            exit(2)

        # Get the sprints for the given scrum board
        logger.debug(f'getting active and future sprints for board {self.args.board}')
        sprints: ResultList[Sprint] = self.jira.sprints(board_id=self.args.board, state='active,future')
        sprints_to_assign = list()
        issues_in_first_sprint = -1 

        for sprint in sprints:
            if issues_in_first_sprint >= 0:
                # we already found the sprint to start with
                sprints_to_assign.append(sprint)
            else:
                issues_in_sprint = len(self.jira.search_issues(
                    f'project = "{self.args.project}" AND sprint = {sprint.id}'
                    f' AND parent = {self.epic.key}'
                ))
                if issues_in_sprint < 2:
                    logger.debug(f'Found first sprint: {sprint}')
                    sprints_to_assign.append(sprint)
                    issues_in_first_sprint = issues_in_sprint
                else:
                    print(f'Found two or more issues in sprint {sprint}. Continue searching...')

        assignee_idx = 0
        for sprint in sprints_to_assign:
            logger.debug(f'Processing sprint {sprint}')
            start_date = datetime.strptime(sprint.startDate, '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.strptime(sprint.endDate, '%Y-%m-%dT%H:%M:%S.%fZ')
            length = end_date - start_date
            logger.debug(f'sprint length {length.days}')
            assignee_email = self.args.assignee[assignee_idx]
            if length.days < 8:
                # Long sprints usually are 10 days (Monday to next Thursday),
                # short ones are 3 days.
                if issues_in_first_sprint == 1:
                    logger.debug('short sprint and first issues already taken')
                    print(f'Continueing, no space in sprint {sprint.name} for another issue')
                else:
                    logger.debug('short sprint can create one issue')
                    self.prepare_and_assign_issue(sprint, assignee_email, 1)
            else:
                if issues_in_first_sprint == 1:
                    logger.debug('long/standard sprint can create one issue for second week')
                    self.prepare_and_assign_issue(sprint, assignee_email, 2)
                else:
                    logger.debug('long/standard sprint can create one two issues')
                    self.prepare_and_assign_issue(sprint, assignee_email, 1)
                    assignee_idx +=1

                    assignee_email = self.args.assignee[assignee_idx]
                    self.prepare_and_assign_issue(sprint, assignee_email, 2)
            issues_in_first_sprint = 0
            assignee_idx +=1
        
        if assignee_idx < len(self.args.assignee):
            print('Not enough sprints to assign the following people')
            while assignee_idx < len(self.args.assignee):
                print(f' - {self.args.assignee[assignee_idx]}')
                assignee_idx +=1
