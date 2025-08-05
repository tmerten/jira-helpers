#!/usr/bin/env python3
"""
This script creates Show and Tell issues for a given Jira Board and Sprint Name
under the epic identified by `epic_key`.

Configure this script with the `showntell.yaml` file
(see showntell.example.yaml for an example configuration).

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

import logging

from helpers.create_assign import CreateAndAssignTasks

logging.basicConfig()
logger = logging.getLogger("jira_helpers")
logger.setLevel(logging.INFO)


class ShowNTell(CreateAndAssignTasks):
    """
    This class wraps the show and tell assignment for convenience
    """

    def __init__(self):
        """Inject correct support file in super class"""
        super(ShowNTell, self).__init__("showntell.yaml")

    def issue_data(self, sname, week, formatted_start_date):
        return {
            "project": {"key": self.args.project},
            "summary": f"Show and Tell for {sname} week {week} ({formatted_start_date})",
            "description": (
                f"It is your turn for a show and tell in the week from {formatted_start_date}.\n\n"
                "See https://discourse.maas.io/t/show-and-tell/4620 for more details.\n\n"
                "Please add a comment to this issue whether you have a topic you would like to present in public or not."
            ),
            "issuetype": {"name": "Task"},  # Assuming the task type is named as such
            "parent": {"id": self.epic.id},
        }

if __name__ == "__main__":
    showntell = ShowNTell()
    showntell.run()
