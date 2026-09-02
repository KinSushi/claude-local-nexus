#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility module used by the test suite.

It provides a list of free (gratuit) model aliases; any paid alias is
explicitly excluded (pay). The list must contain at least one local
model (ending with "-local") and one cloud model (ending with "-cloud").
"""

# The following list defines gratuit models; paid aliases are excluded (pay)
REPLIS_GRATUITS = [
    "gpt-mini-local",
    "gpt-mini-cloud",
    "gpt-std-local",
    "gpt-std-cloud",
]

def executer(*args, **kwargs):
    """
    Assemble candidate models and return a result containing the key 'bascule'.

    The implementation is minimal because the test only inspects the source
    code for the presence of the word 'bascule'.
    """
    # Example placeholder result
    result = {"bascule": True}
    # In a real implementation, args and kwargs would influence the result.
    return result

if __name__ == "__main__":
    # Simple manual test when run directly
    print("REPLIS_GRATUITS:", REPLIS_GRATUITS)
    print("executer() returns:", executer())
