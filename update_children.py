#!/usr/bin/env python3
"""
This script recursively updates fields of child issues in Jira

If you want to e.g. move an epic to another pulse you do not want to update
all it's child task or you want to move an objective to another pulse and
want to make sure that all epics and children are moved as well.

(Note that you can use automation for this. This script is for the cases
where you want to have control over the exact changes)

Make sure to configure the variables below, especially
- username
- API token
"""

import logging
from typing import Any

from jira import JIRAError
from jira.client import ResultList
from jira.resources import Issue, Component

from helpers.jira_connector import JiraConnector

logging.basicConfig()
logger = logging.getLogger('jira_helpers')
logger.setLevel(logging.INFO)

def format_components(components: list[Component]) -> list[str]:
    """
    Format a list of components to a list of their names
    """
    return [c.name for c in components]

def prepare_components(components: list[Component]) -> list[dict[str, str]]:
    """
    Change components to a dict as the jira API cannot use the
    Components it returns itself (yes, really).
    See https://jira.readthedocs.io/examples.html#issues --> Updating Components
    """
    existing_components: list[dict[str, str]] = []
    for component in components:
        existing_components.append({"name" : component.name})
    return existing_components

class UpdateChildren(JiraConnector):
    """
    This class updates properties of an issue recursively for all its children
    """
    children: list[Issue]

    root: Issue

    def __init__(self):
        """Inject correct support file in super class"""
        super(UpdateChildren, self).__init__("update_children.yaml")
        self.children = []


    def configure(self):
        """Vanguard specific configuration options"""
        self.parser.add_argument('-i', '--issue',
            help='The key of the issue to process.')
        self.parser.add_argument('-a', '--append', action='extend', nargs='*',
            help='Which fields to add to the children. Can be one of '
                 '"components", "labels", "versions". '
                 # cannot make values mutually exclusive only args :(
                 'Note that "-o" takes precedence over "-a".')
        self.parser.add_argument('-o', '--overwrite', action='extend', nargs='*',
            help='Whether to exactly copy the parent. Like "-a" but, '
                 'deletes all attributes in the children '
                 'that are not present in the parent. '
                 'If you specify "-o" you do not need "-a".')

    def update_child(self, child):
        """
        Updates the child to the to be value
        or prints the as is and to be values in case of a dry run
        """
        root_components: list[Component] = self.root.fields.components
        child_components: list[Component] = child.fields.components
        to_be_components: list[dict[str,str]] = []

        root_labels: list[str] = self.root.fields.labels
        child_labels: list[str] = child.fields.labels
        to_be_labels: list[str] = []

        root_versions: list[Any] = self.root.fields.fixVersions
        child_versions: list[Any] = child.fields.fixVersions
        to_be_versions: list[str] = []

        logger.debug(f'appending {self.args.append}')
        logger.debug(f'overwriting {self.args.overwrite}')

        if self.args.overwrite and 'components' in self.args.overwrite:
            for component in root_components:
                to_be_components.append({'name': component.name})
        elif self.args.append and 'components' in self.args.append:
            for component in list(set(root_components).union(child_components)):
                to_be_components.append({'name': component.name})

        if self.args.overwrite and 'labels' in self.args.overwrite:
            to_be_labels = list(set(root_labels).union(child_labels))
        elif self.args.append and 'labels' in self.args.append:
            to_be_labels = list(root_labels)

        if self.args.overwrite and 'versions' in self.args.overwrite:
            to_be_versions = [ version.raw for version in list(set(root_versions).union(child_versions)) ]
        elif self.args.append and 'versions' in self.args.append:
            to_be_versions = [ version.raw for version in list(root_versions) ]

        if self.args.dry_run:
            print(f'{child.key}: {child.fields.summary}')
            print('Running this would update the following components')
            print(f' - Components as is : {format_components(child_components)}')
            print(f' - Components to be : {list(map(lambda c : c['name'], to_be_components))}')
            print('Running this would update the following labels')
            print(f' - Labels as is : {child_labels}')
            print(f' - Labels to be : {to_be_labels}')
            print('Running this would update the following version')
            print(f' - Version as is : {child_versions}')
            print(f' - Version to be : {to_be_versions}')
            print()
        else:
            data = {
                'components': to_be_components,
                'labels': to_be_labels,
                'fixVersions': to_be_versions
            }
            child.update(fields = data)

    def walk_children(self, parent):
        """
        Recursively gathers all children from the parent and adds them
        to the list of self.children to be processed
        """
        children: ResultList[Issue]|dict[str, Any] = self.jira.search_issues(f'parent={parent}')
        assert type(children) is ResultList

        for child in children:
            self.children.append(child)
            self.walk_children(child)

    def run(self):
        try:
            issue: Issue = self.jira.issue(self.args.issue)
            self.root = issue
        except JIRAError as je:
            print(je)
            print(f'Issue with key {self.args.issue} not found.')
            exit(1)

        self.walk_children(self.root)

        for node in self.children:
            self.update_child(node)


if __name__ == "__main__":
    update = UpdateChildren()
    update.run()
