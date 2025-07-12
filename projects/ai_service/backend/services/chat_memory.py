import json
import os

# Simple in-memory chat memory for each session/user
# This is a stub for future persistent or advanced memory

class ChatMemory:
    def __init__(self, max_length=20, persist_path=None):
        self.memory = {}
        self.max_length = max_length
        self.persist_path = persist_path
        if self.persist_path and os.path.exists(self.persist_path):
            self.load_from_disk()

    def add_message(self, session_id, message):
        # message: dict with keys: text, file (optional), metadata (optional)
        if session_id not in self.memory:
            self.memory[session_id] = []
        self.memory[session_id].append(message)
        if len(self.memory[session_id]) > self.max_length:
            self.memory[session_id] = self.memory[session_id][-self.max_length:]
        if self.persist_path:
            self.save_to_disk()

    def get_memory(self, session_id):
        return self.memory.get(session_id, [])

    def clear_memory(self, session_id):
        if session_id in self.memory:
            del self.memory[session_id]
            if self.persist_path:
                self.save_to_disk()

    def save_to_disk(self):
        with open(self.persist_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f)

    def load_from_disk(self):
        with open(self.persist_path, 'r', encoding='utf-8') as f:
            self.memory = json.load(f)
