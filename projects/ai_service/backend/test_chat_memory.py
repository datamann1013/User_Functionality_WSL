import pytest
from services.chat_memory import ChatMemory

def test_add_and_get_memory():
    mem = ChatMemory(max_length=3)
    mem.add_message('session1', 'hello')
    mem.add_message('session1', 'world')
    assert mem.get_memory('session1') == ['hello', 'world']
    mem.add_message('session1', 'again')
    mem.add_message('session1', 'overflow')
    # Should only keep the last 3 messages
    assert mem.get_memory('session1') == ['world', 'again', 'overflow']

def test_clear_memory():
    mem = ChatMemory()
    mem.add_message('s', 'msg')
    mem.clear_memory('s')
    assert mem.get_memory('s') == []
    # Clearing non-existent session should not error
    mem.clear_memory('nope')

def test_multiple_sessions():
    mem = ChatMemory()
    mem.add_message('a', '1')
    mem.add_message('b', '2')
    assert mem.get_memory('a') == ['1']
    assert mem.get_memory('b') == ['2']

