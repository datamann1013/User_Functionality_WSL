import pytest
from core.scheduler import RoundRobinScheduler

def test_round_robin_basic():
    rr = RoundRobinScheduler(['a', 'b', 'c'])
    assert rr.next() == 'a'
    assert rr.next() == 'b'
    assert rr.next() == 'c'
    assert rr.next() == 'a'  # wraps around
    assert rr.next() == 'b'

def test_empty_scheduler():
    rr = RoundRobinScheduler([])
    assert rr.next() is None
    rr = RoundRobinScheduler()
    assert rr.next() is None

def test_set_items_and_reset():
    rr = RoundRobinScheduler(['x', 'y'])
    assert rr.next() == 'x'
    rr.set_items(['a', 'b', 'c'])
    assert rr.next() == 'a'
    rr.next()
    rr.reset()
    assert rr.next() == 'a'

def test_len():
    rr = RoundRobinScheduler(['a', 'b'])
    assert len(rr) == 2
    rr.set_items(['x'])
    assert len(rr) == 1
    rr.set_items([])
    assert len(rr) == 0

