#!/usr/bin/env python3
"""Test script for AI Service chat functionality with model"""

import requests
import json

# Test chat endpoint
def test_chat():
    url = "http://127.0.0.1:5000/api/chat"
    
    test_messages = [
        {"message": "Hello! Who are you?", "agent_id": "assistant-1"},
        {"message": "What model are you using?", "agent_id": "assistant-1"},
        {"message": "Test the system", "agent_id": "assistant-1"}
    ]
    
    print("🧪 Testing AI Service Chat with Model Integration")
    print("=" * 50)
    
    for i, test_data in enumerate(test_messages, 1):
        print(f"\n📨 Test {i}: {test_data['message']}")
        
        try:
            response = requests.post(url, json=test_data)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"🤖 Response: {data.get('response', 'No response')}")
                print(f"🎯 Model: {data.get('model_name', 'Unknown')} (ID: {data.get('model_id', 'Unknown')})")
                print(f"🕒 Timestamp: {data.get('timestamp', 'Unknown')}")
                print(f"⚙️ Mode: {data.get('mode', 'Unknown')}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection failed - Backend not running?")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    print("\n" + "=" * 50)
    print("✅ Chat functionality test completed!")
    return True

if __name__ == "__main__":
    test_chat()
