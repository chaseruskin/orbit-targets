"""
Wrapper module for accessing/modifying environment variables.
"""

import os


class KvPair:
    """
    A key-value pair, useful for storing generics/parameters provided on the command-line.
    """
    def __init__(self, key: str, val: str):
        self.key = key
        self.val = val

    @staticmethod
    def from_str(s: str):
        # split on equal sign
        words = s.split('=', 1)
        if len(words) != 2:
            return None
        return KvPair(words[0], words[1])
    
    @staticmethod
    def from_arg(s: str):
        import argparse
        result = KvPair.from_str(s)
        if result is None:
            msg = "key-value pair "+__quote_str(s)+" is missing <value>"
            raise argparse.ArgumentTypeError(msg)
        return result

    def to_str(self) -> str:
        return self.key+'='+self.val
    
    def __str__(self):
        return self.key+'='+self.val
    
    @staticmethod
    def into_dict(pairs: list) -> dict:
        """
        Takes a list of KvPair instances and translates them into a dictionary.
        """
        result = {}
        for p in pairs:
            result[p.key] = p.val
        return result


def read(key: str, default: str=None, missing_ok: bool=True) -> None:
    try:
        value = os.environ[key]
    except KeyError:
        value = None
    # do not allow empty values to trigger variable
    if value is not None and len(value) == 0:
        value = None
    if value is None:
        if missing_ok == False:
            exit("error: environment variable "+__quote_str(key)+" does not exist")
        else:
            value = default
    return value


def write(key: str, value: str):
    os.environ[key] = str(value)


def prepend(key, value: str):
    """
    Adds the `value` to the start of the environment variable `key`.

    Uses the path separator for the OS to separate items.
    """
    if value is not None and os.path.exists(value) and len(value) > 0 and (os.getenv(key) is None or value not in os.getenv(key)):
        if os.getenv(key) is None:
            os.environ[key] = value + os.pathsep
        else:
            os.environ[key] = value + os.pathsep + os.environ[key]


def append(key, value: str):
    """
    Adds the `value` to the end of the environment variable `key`.

    Uses the path separator for the OS to separate items.
    """
    if value is not None and os.path.exists(value) and len(value) > 0 and (os.getenv(key) is None or value not in os.getenv(key)):
        if os.getenv(key) is None:
            os.environ[key] = value
        else:
            os.environ[key] += os.pathsep + value


def __quote_str(s: str) -> str:
    """
    Wraps the string `s` around double quotes `\"` characters."
    """
    return '\"' + s + '\"'
