# Simple in-memory chat memory for each session/user
# This is a stub for future persistent or advanced memory

class ChatMemory:
    def __init__(self, max_length=20):
        self.memory = {}
        self.max_length = max_length

    def add_message(self, session_id, message):
        if session_id not in self.memory:
            self.memory[session_id] = []
        self.memory[session_id].append(message)
        if len(self.memory[session_id]) > self.max_length:
            self.memory[session_id] = self.memory[session_id][-self.max_length:]

    def get_memory(self, session_id):
        return self.memory.get(session_id, [])

    def clear_memory(self, session_id):
        if session_id in self.memory:
            del self.memory[session_id]

