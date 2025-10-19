#!/usr/bin/env python3
"""
CPU Benchmark Collection Script for RuneCore Ecosystem
Measures CPU usage patterns and performance metrics across system components
"""

import json
import os
import sys
import time
import psutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CPUBenchmark:
    """Collects and analyzes CPU performance metrics for RuneCore components"""
    
    def __init__(self, output_dir: str = "benchmarks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.platform = self._get_platform_info()
        self.cpu_count = psutil.cpu_count()
        self.cpu_count_logical = psutil.cpu_count(logical=True)
        
    def _get_platform_info(self) -> str:
        """Get standardized platform identifier"""
        import platform
        system = platform.system().lower()
        arch = platform.machine()
        return f"{system}-{arch}"
    
    def _get_cpu_info(self) -> Dict[str, any]:
        """Get detailed CPU information"""
        import platform
        
        # Get CPU frequencies
        try:
            cpu_freq = psutil.cpu_freq()
            freq_info = {
                "current_mhz": cpu_freq.current if cpu_freq else 0,
                "min_mhz": cpu_freq.min if cpu_freq else 0,
                "max_mhz": cpu_freq.max if cpu_freq else 0
            }
        except:
            freq_info = {"current_mhz": 0, "min_mhz": 0, "max_mhz": 0}
        
        return {
            "processor": platform.processor(),
            "physical_cores": self.cpu_count,
            "logical_cores": self.cpu_count_logical,
            "frequency": freq_info,
            "architecture": platform.architecture()[0],
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
    
    def _monitor_cpu_usage(self, duration: int, interval: float = 0.1) -> List[Dict[str, any]]:
        """Monitor CPU usage over specified duration"""
        samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Get per-CPU usage
            cpu_percent = psutil.cpu_percent(interval=interval, percpu=True)
            
            # Get overall system stats
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            
            sample = {
                "timestamp": time.time(),
                "cpu_percent_total": sum(cpu_percent) / len(cpu_percent),
                "cpu_percent_per_core": cpu_percent,
                "load_average_1m": load_avg[0],
                "load_average_5m": load_avg[1],
                "load_average_15m": load_avg[2]
            }
            samples.append(sample)
        
        return samples
    
    def _calculate_cpu_metrics(self, samples: List[Dict[str, any]]) -> Dict[str, float]:
        """Calculate CPU performance metrics from samples"""
        if not samples:
            return {}
        
        cpu_values = [s['cpu_percent_total'] for s in samples]
        load_values = [s['load_average_1m'] for s in samples]
        
        return {
            "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
            "max_cpu_percent": max(cpu_values),
            "min_cpu_percent": min(cpu_values),
            "cpu_variance": self._calculate_variance(cpu_values),
            "avg_load": sum(load_values) / len(load_values),
            "max_load": max(load_values),
            "samples_count": len(samples)
        }
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    def _run_cpu_stress_test(self, duration: int = 5) -> Dict[str, any]:
        """Run a controlled CPU stress test"""
        print(f"  Running {duration}s CPU stress test...")
        
        def cpu_worker():
            """CPU intensive worker function"""
            end_time = time.time() + duration
            while time.time() < end_time:
                # Perform CPU-intensive calculations
                for i in range(10000):
                    _ = i ** 2
        
        # Start monitoring before stress test
        baseline_samples = self._monitor_cpu_usage(2, 0.2)
        baseline_metrics = self._calculate_cpu_metrics(baseline_samples)
        
        # Start stress test threads (one per core)
        threads = []
        for _ in range(self.cpu_count):
            thread = threading.Thread(target=cpu_worker)
            threads.append(thread)
        
        # Start stress test and monitoring
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        stress_samples = self._monitor_cpu_usage(duration, 0.2)
        
        # Wait for stress test to complete
        for thread in threads:
            thread.join()
        
        # Monitor recovery
        recovery_samples = self._monitor_cpu_usage(2, 0.2)
        
        stress_metrics = self._calculate_cpu_metrics(stress_samples)
        recovery_metrics = self._calculate_cpu_metrics(recovery_samples)
        
        return {
            "baseline": baseline_metrics,
            "stress": stress_metrics,
            "recovery": recovery_metrics,
            "stress_duration": duration,
            "cores_used": self.cpu_count
        }
    
    def benchmark_ai_service(self) -> Dict[str, any]:
        """Benchmark AI service CPU performance"""
        print("🔍 Benchmarking AI Service CPU performance...")
        
        ai_process = None
        try:
            # Start AI service
            ai_process = subprocess.Popen([
                sys.executable, "projects/ai_service/backend/app.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            time.sleep(3)  # Allow service to start
            
            # Monitor CPU usage during normal operation
            print("  Monitoring normal operation...")
            normal_samples = self._monitor_cpu_usage(10, 0.5)
            normal_metrics = self._calculate_cpu_metrics(normal_samples)
            
            # Get process-specific CPU usage
            try:
                process = psutil.Process(ai_process.pid)
                process_cpu = process.cpu_percent(interval=1.0)
            except:
                process_cpu = 0
            
            return {
                "component": "ai_service",
                "normal_operation": normal_metrics,
                "process_cpu_percent": process_cpu,
                "efficiency_score": self._calculate_cpu_efficiency(normal_metrics),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "component": "ai_service",
                "error": str(e),
                "status": "failed"
            }
        finally:
            if ai_process:
                ai_process.terminate()
                ai_process.wait(timeout=5)
    
    def benchmark_error_logger(self) -> Dict[str, any]:
        """Benchmark ErrorLogger CPU performance"""
        print("🔍 Benchmarking ErrorLogger CPU performance...")
        
        try:
            # Import ErrorLogger
            sys.path.append("projects/ErrorLogger")
            
            # Monitor CPU during logger operations
            def logger_workload():
                try:
                    from logger import ErrorLogger
                    logger = ErrorLogger()
                    
                    # Generate test logs
                    for i in range(500):
                        logger.log_error(f"PERF_TEST_{i}", f"Performance test error {i}")
                        if i % 100 == 0:
                            time.sleep(0.01)  # Small pause every 100 logs
                except:
                    pass
            
            # Run workload while monitoring
            workload_thread = threading.Thread(target=logger_workload)
            
            baseline_samples = self._monitor_cpu_usage(2, 0.2)
            
            workload_thread.start()
            workload_samples = self._monitor_cpu_usage(5, 0.2)
            workload_thread.join()
            
            recovery_samples = self._monitor_cpu_usage(2, 0.2)
            
            baseline_metrics = self._calculate_cpu_metrics(baseline_samples)
            workload_metrics = self._calculate_cpu_metrics(workload_samples)
            recovery_metrics = self._calculate_cpu_metrics(recovery_samples)
            
            return {
                "component": "error_logger",
                "baseline": baseline_metrics,
                "workload": workload_metrics,
                "recovery": recovery_metrics,
                "efficiency_score": self._calculate_cpu_efficiency(workload_metrics),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "component": "error_logger",
                "error": str(e),
                "status": "failed"
            }
    
    def benchmark_system_stress(self) -> Dict[str, any]:
        """Benchmark system under stress conditions"""
        print("🔍 Running system stress benchmark...")
        
        try:
            stress_results = self._run_cpu_stress_test(10)
            
            return {
                "component": "system_stress",
                "stress_test": stress_results,
                "thermal_throttling_detected": self._detect_thermal_throttling(stress_results),
                "performance_score": self._calculate_performance_score(stress_results),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "component": "system_stress",
                "error": str(e),
                "status": "failed"
            }
    
    def _calculate_cpu_efficiency(self, metrics: Dict[str, float]) -> float:
        """Calculate CPU efficiency score (0-100)"""
        if not metrics:
            return 0.0
        
        avg_cpu = metrics.get('avg_cpu_percent', 100)
        variance = metrics.get('cpu_variance', 100)
        
        # Lower CPU usage and variance = higher efficiency
        efficiency = max(0, 100 - avg_cpu) * max(0, 100 - variance * 10) / 100
        return min(100, efficiency)
    
    def _detect_thermal_throttling(self, stress_results: Dict[str, any]) -> bool:
        """Detect if thermal throttling occurred during stress test"""
        stress_metrics = stress_results.get('stress', {})
        baseline_metrics = stress_results.get('baseline', {})
        
        if not stress_metrics or not baseline_metrics:
            return False
        
        # Look for significant drop in max CPU usage during stress
        stress_max = stress_metrics.get('max_cpu_percent', 0)
        expected_max = min(100, baseline_metrics.get('max_cpu_percent', 0) * 5)
        
        return stress_max < expected_max * 0.7
    
    def _calculate_performance_score(self, stress_results: Dict[str, any]) -> float:
        """Calculate overall performance score based on stress test"""
        stress_metrics = stress_results.get('stress', {})
        recovery_metrics = stress_results.get('recovery', {})
        
        if not stress_metrics:
            return 0.0
        
        # Score based on sustained performance and recovery
        sustained_perf = stress_metrics.get('avg_cpu_percent', 0)
        recovery_speed = 100 - recovery_metrics.get('avg_cpu_percent', 100)
        
        score = (sustained_perf + recovery_speed) / 2
        return min(100, max(0, score))
    
    def run_comprehensive_benchmark(self) -> Dict[str, any]:
        """Run comprehensive CPU benchmark across all components"""
        print("🚀 Starting comprehensive CPU benchmark...")
        
        timestamp = datetime.now(timezone.utc).isoformat()
        cpu_info = self._get_cpu_info()
        
        # Run component benchmarks
        benchmarks = {
            "ai_service": self.benchmark_ai_service(),
            "error_logger": self.benchmark_error_logger(),
            "system_stress": self.benchmark_system_stress()
        }
        
        # Calculate overall performance metrics
        efficiency_scores = [
            b.get('efficiency_score', 0)
            for b in benchmarks.values()
            if b.get('status') == 'success' and 'efficiency_score' in b
        ]
        
        performance_scores = [
            b.get('performance_score', 0)
            for b in benchmarks.values()
            if b.get('status') == 'success' and 'performance_score' in b
        ]
        
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0
        avg_performance = sum(performance_scores) / len(performance_scores) if performance_scores else 0
        
        results = {
            "timestamp": timestamp,
            "platform": self.platform,
            "cpu_info": cpu_info,
            "component_benchmarks": benchmarks,
            "summary": {
                "average_efficiency_score": avg_efficiency,
                "average_performance_score": avg_performance,
                "overall_score": (avg_efficiency + avg_performance) / 2,
                "successful_benchmarks": sum(1 for b in benchmarks.values() if b.get('status') == 'success'),
                "failed_benchmarks": sum(1 for b in benchmarks.values() if b.get('status') == 'failed'),
                "thermal_throttling_detected": benchmarks.get('system_stress', {}).get('thermal_throttling_detected', False)
            }
        }
        
        return results
    
    def save_results(self, results: Dict[str, any]) -> str:
        """Save benchmark results to file"""
        filename = f"cpu-{self.platform}-{int(time.time())}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"📊 CPU benchmark results saved to: {filepath}")
        return str(filepath)


def main():
    """Main benchmark execution"""
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "benchmarks"
    
    benchmark = CPUBenchmark(output_dir)
    results = benchmark.run_comprehensive_benchmark()
    filepath = benchmark.save_results(results)
    
    # Print summary
    summary = results['summary']
    cpu_info = results['cpu_info']
    
    print(f"\n📈 CPU Benchmark Summary:")
    print(f"   Platform: {results['platform']}")
    print(f"   CPU: {cpu_info['physical_cores']} cores ({cpu_info['logical_cores']} logical)")
    print(f"   Efficiency Score: {summary['average_efficiency_score']:.1f}/100")
    print(f"   Performance Score: {summary['average_performance_score']:.1f}/100")
    print(f"   Overall Score: {summary['overall_score']:.1f}/100")
    print(f"   Successful Tests: {summary['successful_benchmarks']}")
    print(f"   Failed Tests: {summary['failed_benchmarks']}")
    
    if summary['thermal_throttling_detected']:
        print("   ⚠️  Thermal throttling detected during stress test")
    
    return 0 if summary['failed_benchmarks'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
