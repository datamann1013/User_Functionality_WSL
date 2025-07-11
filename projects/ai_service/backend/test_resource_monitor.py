from core.resource_monitor import get_available_resources, can_launch_model

def test_get_available_resources_keys():
    resources = get_available_resources()
    assert 'cpu_percent' in resources
    assert 'ram_mb' in resources
    assert 'gpu_percent' in resources
    assert 0 <= resources['cpu_percent'] <= 100
    assert 0 <= resources['gpu_percent'] <= 100
    assert 1000 <= resources['ram_mb'] <= 16000

def test_can_launch_model():
    # Since RAM is random, test both possible outcomes
    result = can_launch_model(required_ram_mb=1000)
    assert isinstance(result, bool)

