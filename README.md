# Jira Helpers

An opinionated set of helpers that I use for my Jira planning work. These helpers have been developed with the Canonical Jira in mind so they for sure will not work for everyone. E.g. they assume two week sprints and possibly other constraints I am not aware of.

## Support Vanguard Helper

The support vanguard helper created weekly issues for a person to be on support and assigns a list of people, usually defined in a `support_vanguard.yaml` file (see `support_vanguard.example.yaml`) to these issues.

This is usually best configured in the `support_vanguard.yaml` file except for credentials and sprint starting number. So it's best run like this:

```sh
JIRA_API_TOKEN="<TOKEN>" uv run support_vanguard.py -h
```

## Show and Tell Helper

This is essentially the same as the Support Vanguard helper with different issue content.

```sh
JIRA_API_TOKEN="<TOKEN>" uv run showntell.py -h
```

## Update Children Helper

This (recursively) updates properties of child issues as defined in the parent issue.

```sh
JIRA_API_TOKEN="<TOKEN>" uv run update_children.py -h
```

## Tipps to run and configure

Every script takes command line arguments. However every argument can also be provided using a configuration file. E.g. `showntell.py` reads `showntell.yaml`. Have a look at the `support_vanguard.example.yaml` file for inspiration.

It is highly recommended to add some config options to the yaml file for convenience, such as the jira username or the sprint template as it uses placeholders that are not easy to provide using the command line.:w

