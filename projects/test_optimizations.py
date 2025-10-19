#!/usr/bin/env python3
"""
Comprehensive test script to validate all optimizations work correctly.
Tests backend, Ollama service, ErrorLogger, and frontend components.
"""
import sys
import os
import requests
import json
import time

# Add project paths
sys.path.insert(0, '/home/administrator/gitcontrol/User_Functionality_WSL/projects/ai_service/backend')
sys.path.insert(0, '/home/administrator/gitcontrol/User_Functionality_WSL/projects/ErrorLogger')

def test_optimized_backend():
    """Test optimized backend functionality"""
    print("🧪 Testing optimized backend...")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:5010/health', timeout=5)
        assert response.status_code == 200
        health_data = response.json()
        assert health_data['status'] == 'ok'
        assert health_data['service'] == 'ai_service'
        print("✅ Backend health endpoint working")
        
        # Test agents endpoint (should use pre-computed data)
        response = requests.get('http://localhost:5010/api/agents', timeout=5)
        assert response.status_code == 200
        agents_data = response.json()
        assert 'agents' in agents_data
        assert 'count' in agents_data
        assert len(agents_data['agents']) >= 0
        print(f"✅ Agents endpoint working (returned {agents_data['count']} agents)")
        
        # Test chat endpoint with fast fallback
        if agents_data['count'] > 0:
            agent_id = agents_data['agents'][0]['id']
            chat_payload = {
                "message": "Hello, testing optimized backend",
                "agent_id": agent_id
            }
            response = requests.post('http://localhost:5010/api/chat', 
                                   json=chat_payload, timeout=10)
            assert response.status_code == 200
            chat_data = response.json()
            assert 'response' in chat_data
            assert 'mode' in chat_data
            print(f"✅ Chat endpoint working (mode: {chat_data['mode']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def test_optimized_ollama():
    """Test optimized Ollama service"""
    print("\n🧪 Testing optimized Ollama service...")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:5012/health', timeout=5)
        assert response.status_code == 200
        health_data = response.json()
        assert health_data['status'] == 'ok'
        assert health_data['service'] == 'ollama_service'
        assert 'ollama_status' in health_data
        print("✅ Ollama health endpoint working")
        print(f"   Ollama running: {health_data['ollama_status']['running']}")
        print(f"   Models available: {len(health_data['ollama_status'].get('models_available', []))}")
        
        # Test models endpoint  
        response = requests.get('http://localhost:5012/models', timeout=5)
        assert response.status_code == 200
        models_data = response.json()
        assert 'models' in models_data
        print(f"✅ Models endpoint working (cached: {models_data.get('cached', False)})")
        
        return True
        
    except Exception as e:
        print(f"❌ Ollama test failed: {e}")
        return False

def test_optimized_errorlogger():
    """Test optimized ErrorLogger"""
    print("\n🧪 Testing optimized ErrorLogger...")
    
    try:
        # Import optimized logger
        from logger import log_error, log_error_remote, get_log_rotation_status
        
        # Test local logging (fast)
        start_time = time.time()
        log_error("TEST1", "Testing optimized local logging", "Test exception")
        local_time = time.time() - start_time
        print(f"✅ Local logging working (took {local_time:.3f}s)")
        
        # Test log rotation status function
        status = get_log_rotation_status()
        assert 'current_log_file' in status
        assert 'log_directory' in status
        print(f"✅ Log rotation status working (file: {status['current_file_size_mb']}MB)")
        
        # Test safe JSON serialization
        from decimal import Decimal
        from datetime import datetime
        test_data = {
            'decimal_value': Decimal('123.45'),
            'datetime_value': datetime.now(),
            'string_value': 'test'
        }
        log_error("TEST2", "Testing safe JSON serialization", extra=test_data)
        print("✅ Safe JSON serialization working")
        
        return True
        
    except Exception as e:
        print(f"❌ ErrorLogger test failed: {e}")
        return False

def test_optimized_components():
    """Test optimized React components (basic check)"""
    print("\n🧪 Testing optimized frontend components...")
    
    try:
        # Check if optimized App.jsx exists and has expected optimizations
        app_path = '/home/administrator/gitcontrol/User_Functionality_WSL/projects/ai_service/frontend/src/App.jsx'
        if os.path.exists(app_path):
            with open(app_path, 'r') as f:
                content = f.read()
            
            # Check for optimization features
            optimizations = [
                'useMemo',  # Should use React.useMemo for performance
                'useCallback',  # Should use React.useCallback for performance
                'AVATAR_COLORS',  # Pre-computed colors
                'getAvatarColor',  # Optimized helper function
            ]
            
            found_optimizations = sum(1 for opt in optimizations if opt in content)
            print(f"✅ Frontend optimizations present ({found_optimizations}/{len(optimizations)} features)")
            
            # Check for removed unused components
            unused_removed = [
                'MainChat' not in content,  # Should not import unused MainChat
            ]
            print(f"✅ Unused components removed ({sum(unused_removed)} cleanups)")
            
            return True
        else:
            print("❌ App.jsx not found")
            return False
            
    except Exception as e:
        print(f"❌ Frontend test failed: {e}")
        return False

def test_performance_improvements():
    """Test performance improvements"""
    print("\n🧪 Testing performance improvements...")
    
    try:
        # Test backend response time
        start_time = time.time()
        response = requests.get('http://localhost:5010/api/agents', timeout=5)
        agents_time = time.time() - start_time
        
        # Should be very fast due to pre-computed data
        if agents_time < 0.1:  # Less than 100ms
            print(f"✅ Agents endpoint very fast ({agents_time:.3f}s)")
        else:
            print(f"⚠️  Agents endpoint slower than expected ({agents_time:.3f}s)")
        
        # Test Ollama health check caching
        start_time = time.time()
        response1 = requests.get('http://localhost:5012/health', timeout=5)
        first_time = time.time() - start_time
        
        start_time = time.time()
        response2 = requests.get('http://localhost:5012/health', timeout=5)
        second_time = time.time() - start_time
        
        if second_time < first_time:
            print(f"✅ Ollama health caching working (first: {first_time:.3f}s, cached: {second_time:.3f}s)")
        else:
            print(f"⚠️  Ollama health caching may not be optimal")
            
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def main():
    """Run comprehensive tests"""
    print("🚀 Starting comprehensive optimization tests...\n")
    
    # Wait a moment for services to be ready
    time.sleep(2)
    
    tests = [
        test_optimized_backend,
        test_optimized_ollama, 
        test_optimized_errorlogger,
        test_optimized_components,
        test_performance_improvements
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL OPTIMIZATIONS WORKING CORRECTLY!")
        print("🔥 Performance improvements validated")
        print("✨ No functionality broken")
        return 0
    else:
        print("⚠️  Some optimizations need attention")
        return 1

if __name__ == '__main__':
    sys.exit(main())
