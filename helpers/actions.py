from argparse import Action
from os import environ

class EnvDefault(Action):
    """
    Adds ability to grab an argument from an environment variable
    as well. Good for tokens and such.

    See https://stackoverflow.com/a/10551190
    """
    def __init__(self, envvar, required=True, default=None, **kwargs):
        if envvar:
            if envvar in environ:
                default = environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


class RequiredOrDefault(Action):
    """
    If there is a default value set (e.g. via the config file),
    make required attributes not required anymore.
    """
    def __init__(self, **kwargs):
        super(RequiredOrDefault, self).__init__(**kwargs)
        if self.default is not None:
            self.required = False

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
