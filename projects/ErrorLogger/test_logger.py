import os
import re
import glob
import pytest
from projects.ErrorLogger import logger
from projects.shared_utils import constants

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))


def get_latest_log_file():
    files = glob.glob(os.path.join(LOG_DIR, 'errorlog_*.log'))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def test_log_file_creation_and_format(monkeypatch):
    # Remove any existing log files
    for f in glob.glob(os.path.join(LOG_DIR, 'errorlog_*.log')):
        os.remove(f)
    # Simulate system boot
    monkeypatch.setattr(logger, 'LOG_FILE_PATH', logger._init_log_file())
    logger.log_error('EABA12', message='Test error')
    log_file = get_latest_log_file()
    assert log_file is not None
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert re.match(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] EABA12: ', content)
    assert 'Test error' in content


def test_log_levels():
    logger.log_error('EABA12', message='Error level')
    logger.log_error('WABA12', message='Warning level')
    logger.log_error('IABA12', message='Info level')
    log_file = get_latest_log_file()
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'EABA12' in content
    assert 'WABA12' in content
    assert 'IABA12' in content


def test_python_exception_logging():
    try:
        1 / 0
    except Exception as e:
        logger.log_error(0, exception=e)
    log_file = get_latest_log_file()
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'ZeroDivisionError' in content


def test_explanation_from_config(monkeypatch):
    # Simulate config explanation
    monkeypatch.setattr(logger, 'get_explanation', lambda code: 'Config explanation')
    logger.log_error('EABA12')
    log_file = get_latest_log_file()
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'Config explanation' in content


def test_log_file_rotates_on_boot(monkeypatch):
    # Simulate boot
    path1 = logger._init_log_file()
    logger.log_error('EABA12', message='First boot')
    path2 = logger._init_log_file()
    logger.log_error('EABA12', message='Second boot')
    assert path1 != path2
    assert os.path.exists(path1)
    assert os.path.exists(path2)
    with open(path2, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'Second boot' in content

