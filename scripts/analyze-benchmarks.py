#!/usr/bin/env python3
"""
Benchmark Analysis Script for RuneCore Ecosystem
Analyzes performance trends and detects regressions in benchmark data
"""

import json
import sys
import glob
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BenchmarkAnalyzer:
    """Analyzes benchmark results and detects performance regressions"""

    def __init__(self, benchmarks_dir: str = "benchmarks"):
        self.benchmarks_dir = Path(benchmarks_dir)
        self.regression_threshold = 1.10  # 10% performance degradation

    def load_benchmark_files(self, benchmark_type: str = None) -> List[Dict[str, any]]:
        """Load all benchmark files of specified type"""
        if benchmark_type:
            pattern = f"{benchmark_type}-*.json"
        else:
            pattern = "*.json"

        files = glob.glob(str(self.benchmarks_dir / pattern))
        benchmarks = []

        for file_path in sorted(files):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    data["_file_path"] = file_path
                    benchmarks.append(data)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")

        return benchmarks

    def get_recent_benchmarks(
        self, benchmarks: List[Dict], days: int = 7
    ) -> List[Dict]:
        """Filter benchmarks to only recent ones"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent = []

        for benchmark in benchmarks:
            try:
                timestamp = datetime.fromisoformat(
                    benchmark["timestamp"].replace("Z", "+00:00")
                )
                if timestamp >= cutoff_date:
                    recent.append(benchmark)
            except:
                # If timestamp parsing fails, include it anyway
                recent.append(benchmark)

        return recent

    def analyze_memory_trends(self, memory_benchmarks: List[Dict]) -> Dict[str, any]:
        """Analyze memory usage trends"""
        if not memory_benchmarks:
            return {"status": "no_data"}

        trends = {}
        components = set()

        # Collect all component names
        for benchmark in memory_benchmarks:
            if "component_benchmarks" in benchmark:
                components.update(benchmark["component_benchmarks"].keys())

        # Analyze trends for each component
        for component in components:
            memory_values = []
            timestamps = []

            for benchmark in memory_benchmarks:
                comp_data = benchmark.get("component_benchmarks", {}).get(component, {})
                if comp_data.get("status") == "success":
                    # Extract memory value (different keys for different components)
                    memory_mb = (
                        comp_data.get("peak_memory_mb")
                        or comp_data.get("estimated_runtime_mb")
                        or comp_data.get("memory_after_logs_mb", 0)
                    )
                    if memory_mb > 0:
                        memory_values.append(memory_mb)
                        timestamps.append(benchmark["timestamp"])

            if len(memory_values) >= 2:
                trend_analysis = self._calculate_trend(memory_values)
                trends[component] = {
                    "current_memory_mb": memory_values[-1],
                    "average_memory_mb": statistics.mean(memory_values),
                    "memory_trend": trend_analysis,
                    "regression_detected": trend_analysis["slope"]
                    > self.regression_threshold - 1,
                    "sample_count": len(memory_values),
                }

        # Calculate overall memory trend
        total_memory_values = []
        for benchmark in memory_benchmarks:
            total = benchmark.get("summary", {}).get("total_estimated_memory_mb", 0)
            if total > 0:
                total_memory_values.append(total)

        overall_trend = (
            self._calculate_trend(total_memory_values)
            if len(total_memory_values) >= 2
            else {}
        )

        return {
            "status": "success",
            "component_trends": trends,
            "overall_trend": overall_trend,
            "regression_detected": any(
                t.get("regression_detected", False) for t in trends.values()
            ),
            "total_benchmarks": len(memory_benchmarks),
        }

    def analyze_cpu_trends(self, cpu_benchmarks: List[Dict]) -> Dict[str, any]:
        """Analyze CPU performance trends"""
        if not cpu_benchmarks:
            return {"status": "no_data"}

        trends = {}
        components = set()

        # Collect all component names
        for benchmark in cpu_benchmarks:
            if "component_benchmarks" in benchmark:
                components.update(benchmark["component_benchmarks"].keys())

        # Analyze trends for each component
        for component in components:
            efficiency_scores = []
            performance_scores = []
            timestamps = []

            for benchmark in cpu_benchmarks:
                comp_data = benchmark.get("component_benchmarks", {}).get(component, {})
                if comp_data.get("status") == "success":
                    if "efficiency_score" in comp_data:
                        efficiency_scores.append(comp_data["efficiency_score"])
                    if "performance_score" in comp_data:
                        performance_scores.append(comp_data["performance_score"])
                    timestamps.append(benchmark["timestamp"])

            if efficiency_scores or performance_scores:
                trends[component] = {}

                if efficiency_scores:
                    efficiency_trend = self._calculate_trend(efficiency_scores)
                    trends[component]["efficiency"] = {
                        "current_score": efficiency_scores[-1],
                        "average_score": statistics.mean(efficiency_scores),
                        "trend": efficiency_trend,
                        "regression_detected": efficiency_trend["slope"]
                        < -(self.regression_threshold - 1),
                    }

                if performance_scores:
                    performance_trend = self._calculate_trend(performance_scores)
                    trends[component]["performance"] = {
                        "current_score": performance_scores[-1],
                        "average_score": statistics.mean(performance_scores),
                        "trend": performance_trend,
                        "regression_detected": performance_trend["slope"]
                        < -(self.regression_threshold - 1),
                    }

        # Calculate overall performance trends
        overall_efficiency = []
        overall_performance = []

        for benchmark in cpu_benchmarks:
            summary = benchmark.get("summary", {})
            if "average_efficiency_score" in summary:
                overall_efficiency.append(summary["average_efficiency_score"])
            if "average_performance_score" in summary:
                overall_performance.append(summary["average_performance_score"])

        overall_trends = {}
        if len(overall_efficiency) >= 2:
            overall_trends["efficiency"] = self._calculate_trend(overall_efficiency)
        if len(overall_performance) >= 2:
            overall_trends["performance"] = self._calculate_trend(overall_performance)

        # Detect any regressions
        regression_detected = False
        for comp_trends in trends.values():
            for metric_trend in comp_trends.values():
                if metric_trend.get("regression_detected", False):
                    regression_detected = True
                    break

        return {
            "status": "success",
            "component_trends": trends,
            "overall_trends": overall_trends,
            "regression_detected": regression_detected,
            "total_benchmarks": len(cpu_benchmarks),
        }

    def _calculate_trend(self, values: List[float]) -> Dict[str, float]:
        """Calculate trend analysis for a series of values"""
        if len(values) < 2:
            return {"slope": 0, "direction": "stable", "confidence": 0}

        # Simple linear regression
        n = len(values)
        x_values = list(range(n))

        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(values)

        numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        # Determine direction and confidence
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        # Calculate R-squared for confidence
        if len(values) > 2:
            predicted = [y_mean + slope * (i - x_mean) for i in x_values]
            ss_res = sum((values[i] - predicted[i]) ** 2 for i in range(n))
            ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
            confidence = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        else:
            confidence = 0.5

        return {
            "slope": slope,
            "direction": direction,
            "confidence": max(0, min(1, confidence)),
        }

    def detect_regressions(
        self, analysis_results: Dict[str, any]
    ) -> List[Dict[str, any]]:
        """Detect and categorize performance regressions"""
        regressions = []

        # Check memory regressions
        if "memory_analysis" in analysis_results:
            memory = analysis_results["memory_analysis"]
            if memory.get("status") == "success":
                for component, trend in memory.get("component_trends", {}).items():
                    if trend.get("regression_detected", False):
                        regressions.append(
                            {
                                "type": "memory",
                                "component": component,
                                "current_value": trend["current_memory_mb"],
                                "average_value": trend["average_memory_mb"],
                                "severity": self._calculate_regression_severity(
                                    trend["current_memory_mb"],
                                    trend["average_memory_mb"],
                                    "memory",
                                ),
                                "trend": trend["memory_trend"],
                            }
                        )

        # Check CPU regressions
        if "cpu_analysis" in analysis_results:
            cpu = analysis_results["cpu_analysis"]
            if cpu.get("status") == "success":
                for component, trends in cpu.get("component_trends", {}).items():
                    for metric, trend_data in trends.items():
                        if trend_data.get("regression_detected", False):
                            regressions.append(
                                {
                                    "type": f"cpu_{metric}",
                                    "component": component,
                                    "current_value": trend_data["current_score"],
                                    "average_value": trend_data["average_score"],
                                    "severity": self._calculate_regression_severity(
                                        trend_data["current_score"],
                                        trend_data["average_score"],
                                        "cpu",
                                    ),
                                    "trend": trend_data["trend"],
                                }
                            )

        return regressions

    def _calculate_regression_severity(
        self, current: float, average: float, metric_type: str
    ) -> str:
        """Calculate regression severity level"""
        if metric_type == "memory":
            # For memory, higher is worse
            ratio = current / average if average > 0 else 1
            if ratio > 1.5:
                return "critical"
            elif ratio > 1.2:
                return "major"
            elif ratio > 1.1:
                return "minor"
        else:
            # For CPU metrics, lower is worse
            ratio = current / average if average > 0 else 1
            if ratio < 0.7:
                return "critical"
            elif ratio < 0.8:
                return "major"
            elif ratio < 0.9:
                return "minor"

        return "negligible"

    def generate_report(self, days: int = 7) -> Dict[str, any]:
        """Generate comprehensive performance analysis report"""
        print(f"🔍 Analyzing benchmark data from the last {days} days...")

        # Load benchmark data
        memory_benchmarks = self.load_benchmark_files("memory")
        cpu_benchmarks = self.load_benchmark_files("cpu")

        # Filter to recent data
        recent_memory = self.get_recent_benchmarks(memory_benchmarks, days)
        recent_cpu = self.get_recent_benchmarks(cpu_benchmarks, days)

        print(
            f"   Found {len(recent_memory)} memory benchmarks, {len(recent_cpu)} CPU benchmarks"
        )

        # Perform analysis
        memory_analysis = self.analyze_memory_trends(recent_memory)
        cpu_analysis = self.analyze_cpu_trends(recent_cpu)

        # Compile results
        analysis_results = {
            "memory_analysis": memory_analysis,
            "cpu_analysis": cpu_analysis,
        }

        # Detect regressions
        regressions = self.detect_regressions(analysis_results)

        # Generate summary
        report = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period_days": days,
            "data_summary": {
                "memory_benchmarks": len(recent_memory),
                "cpu_benchmarks": len(recent_cpu),
                "total_benchmarks": len(recent_memory) + len(recent_cpu),
            },
            "memory_analysis": memory_analysis,
            "cpu_analysis": cpu_analysis,
            "regressions": regressions,
            "summary": {
                "total_regressions": len(regressions),
                "critical_regressions": len(
                    [r for r in regressions if r["severity"] == "critical"]
                ),
                "major_regressions": len(
                    [r for r in regressions if r["severity"] == "major"]
                ),
                "minor_regressions": len(
                    [r for r in regressions if r["severity"] == "minor"]
                ),
                "overall_status": "healthy" if not regressions else "degraded",
            },
        }

        return report

    def save_report(self, report: Dict[str, any]) -> str:
        """Save analysis report to file"""
        timestamp = int(datetime.now().timestamp())
        filename = f"analysis-{timestamp}.json"
        filepath = self.benchmarks_dir / filename

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"📊 Analysis report saved to: {filepath}")
        return str(filepath)


def main():
    """Main analysis execution"""
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    benchmarks_dir = sys.argv[2] if len(sys.argv) > 2 else "benchmarks"

    analyzer = BenchmarkAnalyzer(benchmarks_dir)
    report = analyzer.generate_report(days)
    filepath = analyzer.save_report(report)

    # Print summary
    summary = report["summary"]
    print(f"\n📈 Performance Analysis Summary:")
    print(f"   Analysis Period: {days} days")
    print(f"   Total Benchmarks: {report['data_summary']['total_benchmarks']}")
    print(f"   Overall Status: {summary['overall_status'].upper()}")
    print(f"   Total Regressions: {summary['total_regressions']}")

    if summary["total_regressions"] > 0:
        print(f"   Critical: {summary['critical_regressions']}")
        print(f"   Major: {summary['major_regressions']}")
        print(f"   Minor: {summary['minor_regressions']}")

        print(f"\n🚨 Detected Regressions:")
        for regression in report["regressions"]:
            print(
                f"   {regression['severity'].upper()}: {regression['component']} "
                f"({regression['type']}) - {regression['current_value']:.1f}"
            )

    return 1 if summary["critical_regressions"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
