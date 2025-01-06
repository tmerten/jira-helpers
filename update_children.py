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
    issue_key: str
    project_key: str
    overwrite: list[str]
    dry_run: bool
    children: list[Issue]

    root: Issue

    def __init__(self):
        """Inject correct support file in super class"""
        super(UpdateChildren, self).__init__("update_children.yaml")


    def configure(self):
        """Vanguard specific configuration options"""
        self.issue_key = self._read_str_from_yaml_or_environment("issue_key")
        self.project_key = self._read_str_from_yaml_or_environment("project_key")
        self.overwrite= self._read_list_from_yaml_or_environment("overwrite")
        self.dry_run = self._read_bool_from_yaml_or_environment("dry_run")
        self.children = []

    def update_child(self, child):
        """
        Updates the child to the to be value
        or prints the as is and to be values in case of a dry run
        """
        root_components: list[Component] = self.root.fields.components
        child_components: list[Component] = child.fields.components
        to_be_components: list[Component]

        root_labels: list[str] = self.root.fields.labels
        child_labels: list[str] = child.fields.labels
        to_be_labels: list[str]

        root_version = self.root.version
        child_version = child.version
        to_be_version = ""

        if 'components' in self.overwrite:
            logger.debug('overwriting components')
            to_be_components = root_components
        else:
            logger.debug('adding root components')
            to_be_components = list(set(root_components).union(child_components))

        if 'labels' in self.overwrite:
            logger.debug('overwriting labels')
            to_be_labels = root_labels
        else:
            logger.debug('adding root labels')
            to_be_labels = list(set(root_labels).union(child_labels))

        # FIXME: if this continues to be the same, this should be generic
        if 'version' in self.overwrite:
            logger.debug('overwriting version')
            to_be_version = root_version
        else:
            logger.debug('adding root labels')
            to_be_version = list(set(root_version).union(child_version))

        if self.dry_run:
            print(f'{child.key}: {child.fields.summary}')
            print(f'Components as is : {format_components(child_components)}')
            print(f'Components to be : {format_components(to_be_components)}')
            print(f'Would update the following labels')
            print(f'Labels as is : {child_labels}')
            print(f'Labels to be : {to_be_labels}')
            print(f'Would update the following version')
            print(f'Version as is : {child_version}')
            print(f'Version to be : {to_be_version}')
            print()
        else:
            child.update(fields = {
                'components': to_be_components,
                'labels': to_be_labels,
                'version': to_be_version
            })

    def walk_children(self, parent):
        children: ResultList[Issue]|dict[str, Any] = self.jira.search_issues(f'parent={parent}')
        assert type(children) is ResultList

        for child in children:
            self.children.append(child)
            self.walk_children(child)

    def run(self):
        try:
            issue: Issue = self.jira.issue(self.issue_key)
            self.root = issue
        except JIRAError:
            print(f'Issue with key {self.issue_key} not found.')
            exit(1)

        self.walk_children(self.root)

        for node in self.children:
            self.update_child(node)
        

if __name__ == "__main__":
    update = UpdateChildren()
    update.run()
