#!/usr/bin/env python3
"""
This script finds all tasks and stories without a parent that have
been stale for a certain time and closes them with a comment.

Make sure to configure the variables below, especially 
- username 
- API token 
"""

import logging
from typing import Any

from jira.client import ResultList
from jira.resources import Issue

from helpers.jira_connector import JiraConnector

logging.basicConfig()
logger = logging.getLogger('jira_helpers')
logger.setLevel(logging.INFO)

class Closer(JiraConnector):
    """
    This class updates properties of an issue recursively for all its children
    """
    # if of the final status, can be 
    # ('11', 'Triaged'), ('21', 'In Progress'), ('31', 'In Review'), ('41', 'Blocked'), ('51', 'To Be Deployed'), ('61', 'Done'), ('71', 'Rejected'), ('81', 'Untriaged')
    def __init__(self):
        """Inject correct support file in super class"""
        super(Closer, self).__init__("close_without_parent.yaml")

    def configure(self):
        """Basic configuration"""
        self.parser.add_argument('-p', '--project-key')
        self.parser.add_argument('-s', '--stale-days', type=int)
        self.parser.add_argument('-t', '--transition-to')

    def run(self):
        issues: ResultList[Issue]|dict[str, Any] = self.jira.search_issues(f'project = "{self.args.project_key}" AND type IN (Task, Story, Bug, Epic) AND status NOT IN (Done, Rejected) AND parent is null AND updated <= -{self.args.stale}d ORDER BY created DESC', maxResults=500)

        print(f'Rejecting {len(issues)} issues with comment:')

        for issue in issues:
            assert type(issue) is Issue or exit(1)
            comment =f'Issue will be closed because it does not have a parent and it has not been updated for {self.args.stale} days'
            if self.args.dry_run:
                print(f' {issue.key} | {issue.fields.issuetype} | {issue.fields.summary}')
                print(f' {comment}')
            else:
                print(f' {issue.key} | {issue.fields.issuetype} | {issue.fields.summary}')
                self.jira.add_comment(issue, comment)
                self.jira.transition_issue(issue, str(self.args.transition_to))
        

if __name__ == "__main__":
    closer = Closer()
    closer.run()
