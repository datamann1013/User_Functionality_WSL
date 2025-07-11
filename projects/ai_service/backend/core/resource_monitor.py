# Simple resource monitor stub for model launching decisions
# In a real system, use psutil or similar for actual resource checks

import random

def get_available_resources():
    """
    Return a mock dictionary of available system resources.
    """
    return {
        'cpu_percent': random.uniform(10, 90),
        'ram_mb': random.randint(1000, 16000),
        'gpu_percent': random.uniform(0, 100),
    }

def can_launch_model(required_ram_mb=4000):
    resources = get_available_resources()
    return resources['ram_mb'] > required_ram_mb

