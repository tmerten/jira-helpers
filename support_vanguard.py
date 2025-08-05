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

import logging

from helpers.create_assign import CreateAndAssignTasks

logging.basicConfig()
logger = logging.getLogger("jira_helpers")
logger.setLevel(logging.INFO)


class Vanguard(CreateAndAssignTasks):
    """
    This class wraps the support vanguard assignment vor convenience
    """

    def __init__(self):
        """Inject correct support file in super class"""
        super(Vanguard, self).__init__("support_vanguard.yaml")

    def issue_data(self, epic, sname, idx, formatted_start_date):
        return {
            "project": {"key": self.args.project},
            "summary": f"Support Vanguard for {sname} week {idx%2 + 1} ({formatted_start_date})",
            "description": (
                f"Provide support Vanguard for the week from {formatted_start_date}.\n\n"
                "See https://discourse.maas.io/t/the-support-vanguard/4658 for more details."
            ),
            "issuetype": {"name": "Task"},  # Assuming the task type is named as such
            "parent": {"id": epic.id},
        }


if __name__ == "__main__":
    vanguard = Vanguard()
    vanguard.run()
