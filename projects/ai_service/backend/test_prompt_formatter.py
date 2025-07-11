from services.prompt_formatter import format_prompt

def test_format_prompt_basic():
    template = "Hello, {name}!"
    variables = {"name": "Alice"}
    assert format_prompt(template, variables) == "Hello, Alice!"

def test_format_prompt_no_variables():
    template = "No variables here."
    assert format_prompt(template) == "No variables here."

def test_format_prompt_missing_variable():
    template = "Hi, {who}!"
    try:
        format_prompt(template, {})
    except KeyError:
        pass
    else:
        assert False, "Should raise KeyError if variable is missing"

