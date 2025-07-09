# ErrorLogger code system constants

# Origins
ERROR_ORIGINS = {
    'A': 'AI Service',
    'H': 'Hidden Toolbar',
    # Add more origins as needed
}

# Components for AI Service
ERROR_COMPONENTS_AI = {
    'B': 'Backend',
    'F': 'Frontend',
    'I': 'Initial Setup',
    'D': 'Docker',
}

# Subcomponents for Backend AI Service
ERROR_B_SUBCOMPONENTS_AI = {
    'A': 'API',
    'C': 'Core',
    'R': 'Registry',
    'S': 'Services',
    '#': 'No Subcomponent',
}

# Example error explanations (non-0 errors)
ERROR_EXPLANATIONS = {
    'ABA12': 'AI Service, Backend, API, error 12: [explanation here]',
    'AF#12': 'AI Service, Frontend, no subcomponent, error 12: [explanation here]',
    # Add more as needed
}

# 0 is reserved for Python exceptions
PYTHON_EXCEPTION_CODE = 0

