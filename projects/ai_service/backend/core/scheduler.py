class RoundRobinScheduler:
    def __init__(self, items=None):
        self.items = list(items) if items else []
        self.index = 0

    def next(self):
        if not self.items:
            return None
        item = self.items[self.index]
        self.index = (self.index + 1) % len(self.items)
        return item

    def set_items(self, items):
        self.items = list(items)
        self.index = 0

    def reset(self):
        self.index = 0

    def __len__(self):
        return len(self.items)

