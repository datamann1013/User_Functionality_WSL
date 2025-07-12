import time


class RoundRobinScheduler:
    def __init__(self, items=None, max_load=2):
        # items: list of dicts with 'id', 'load', 'last_used'
        self.items = list(items) if items else []
        self.index = 0
        self.max_load = max_load

    def next(self):
        if not self.items:
            return None
        n = len(self.items)
        for _ in range(n):
            item = self.items[self.index]
            self.index = (self.index + 1) % n
            if item.get('load', 0) < self.max_load:
                item['last_used'] = time.time()
                item['load'] = item.get('load', 0) + 1
                return item
        return None  # All overloaded

    def release(self, model_id):
        for item in self.items:
            if item['id'] == model_id:
                item['load'] = max(0, item.get('load', 0) - 1)

    def set_items(self, items):
        self.items = list(items)
        self.index = 0

    def reset(self):
        self.index = 0

    def __len__(self):
        return len(self.items)
