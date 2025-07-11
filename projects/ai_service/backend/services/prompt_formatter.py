# Simple prompt formatter stub
# Supports dynamic prompt formatting and file/datasheet injection (future)

def format_prompt(template, variables=None):
    """
    Replace {placeholders} in template with values from variables dict.
    Raises KeyError if a required variable is missing.
    """
    if variables is None:
        variables = {}
    return template.format(**variables)
