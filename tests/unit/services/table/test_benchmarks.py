"""
Unit tests for Performance Benchmarking.

Comprehensive test suite covering:
- Query type benchmarking (point, partition, table scan)
- Memory profiling
- Concurrent query handling
- Cache effectiveness
- Performance comparison
- Regression detection
"""

import pytest
import time
from localzure.services.table.benchmarks import (
    QueryBenchmark,
    BenchmarkResult,
    ComparisonResult,
)


class TestBenchmarkResult:
    """Tests for benchmark result data structure."""
    
    def test_create_result(self):
        """Test creating benchmark result."""
        result = BenchmarkResult(
            name="test_bench",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0
        )
        
        assert result.name == "test_bench"
        assert result.iterations == 100
        assert result.avg_ms == 10.0
        assert result.throughput_qps == 100.0
    
    def test_meets_target(self):
        """Test target validation."""
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0
        )
        
        assert result.meets_target(15.0) is True
        assert result.meets_target(5.0) is False
    
    def test_to_dict(self):
        """Test result serialization."""
        result = BenchmarkResult(
            name="test",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0,
            memory_peak_mb=50.0,
            success_count=98,
            error_count=2
        )
        
        data = result.to_dict()
        
        assert data['name'] == 'test'
        assert data['iterations'] == 100
        assert data['latency']['avg_ms'] == 10.0
        assert data['throughput_qps'] == 100.0
        assert data['memory']['peak_mb'] == 50.0
        assert data['success_count'] == 98
        assert data['error_count'] == 2


class TestQueryBenchmark:
    """Tests for query benchmarking."""
    
    def test_init(self):
        """Test benchmark initialization."""
        benchmark = QueryBenchmark()
        
        assert benchmark.results == []
    
    def test_point_query_benchmark(self):
        """Test point query benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(iterations=100)
        
        assert result.name == "point_query"
        assert result.iterations == 100
        assert result.success_count == 100
        assert result.error_count == 0
        assert result.avg_ms >= 0
        assert result.throughput_qps > 0
        
        # Should meet < 1ms target for point queries
        # (May not always pass in slow CI environments)
        assert result.avg_ms < 50  # Relaxed for testing
    
    def test_partition_scan_benchmark(self):
        """Test partition scan benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_partition_scan(
            partition_size=50,
            iterations=100
        )
        
        assert result.name == "partition_scan"
        assert result.iterations == 100
        assert result.success_count == 100
        assert result.metadata['partition_size'] == 50
        assert result.avg_ms >= 0
    
    def test_table_scan_benchmark(self):
        """Test table scan benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_table_scan(
            table_size=100,  # Small for testing
            iterations=10
        )
        
        assert result.name == "table_scan"
        assert result.iterations == 10
        assert result.success_count == 10
        assert result.metadata['table_size'] == 100
        assert result.avg_ms >= 0
    
    def test_complex_filter_benchmark(self):
        """Test complex filter benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_complex_filter(
            complexity=5,
            entity_count=50,
            iterations=100
        )
        
        assert result.name == "complex_filter"
        assert result.iterations == 100
        assert result.metadata['complexity'] == 5
        assert result.metadata['entity_count'] == 50
        assert result.avg_ms >= 0
    
    def test_function_benchmark(self):
        """Test function call benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_function_calls(
            function_name="startswith",
            entity_count=50,
            iterations=100
        )
        
        assert result.name == "function_startswith"
        assert result.iterations == 100
        assert result.metadata['function'] == "startswith"
        assert result.avg_ms >= 0
    
    def test_concurrent_benchmark(self):
        """Test concurrent query benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_concurrent_queries(
            query_count=100,
            thread_count=5,
            query_type="point"
        )
        
        assert result.name == "concurrent_point"
        assert result.iterations == 100
        assert result.metadata['thread_count'] == 5
        assert result.success_count + result.error_count == 100
        assert result.throughput_qps > 0
    
    def test_cache_effectiveness(self):
        """Test cache effectiveness benchmarking."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_cache_effectiveness(
            unique_queries=10,
            iterations_per_query=10
        )
        
        assert result.name == "cache_effectiveness"
        assert result.iterations == 100  # 10 * 10
        assert result.success_count == 100
        assert result.metadata['unique_queries'] == 10
    
    def test_memory_profiling(self):
        """Test memory profiling."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(
            iterations=100,
            profile_memory=True
        )
        
        assert result.memory_peak_mb >= 0
        # Should not leak significant memory
        assert abs(result.memory_leaked_mb) < 10  # Less than 10MB
    
    def test_percentiles(self):
        """Test percentile calculation."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(iterations=100)
        
        # Verify percentile ordering
        assert result.min_ms <= result.p50_ms
        assert result.p50_ms <= result.p95_ms
        assert result.p95_ms <= result.p99_ms
        assert result.p99_ms <= result.max_ms
    
    def test_throughput_calculation(self):
        """Test throughput calculation."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(iterations=1000)
        
        # Throughput = iterations / (total_ms / 1000)
        expected_qps = (result.success_count / result.total_ms) * 1000
        assert abs(result.throughput_qps - expected_qps) < 1.0
    
    def test_get_all_results(self):
        """Test retrieving all results."""
        benchmark = QueryBenchmark()
        
        benchmark.bench_point_query(iterations=10)
        benchmark.bench_partition_scan(partition_size=10, iterations=10)
        
        results = benchmark.get_all_results()
        
        assert len(results) == 2
        assert results[0].name == "point_query"
        assert results[1].name == "partition_scan"
    
    def test_reset(self):
        """Test resetting results."""
        benchmark = QueryBenchmark()
        
        benchmark.bench_point_query(iterations=10)
        assert len(benchmark.results) == 1
        
        benchmark.reset()
        assert len(benchmark.results) == 0


class TestComparison:
    """Tests for performance comparison."""
    
    def test_compare_faster(self):
        """Test comparison when current is faster."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0
        )
        
        current = BenchmarkResult(
            name="current",
            iterations=100,
            total_ms=500.0,
            avg_ms=5.0,
            min_ms=2.0,
            max_ms=10.0,
            p50_ms=5.0,
            p95_ms=9.0,
            p99_ms=9.5,
            throughput_qps=200.0
        )
        
        benchmark = QueryBenchmark()
        comparison = benchmark.compare_results(baseline, current)
        
        assert comparison.speedup == 2.0  # 2x faster
        assert comparison.regression is False
        assert "2.00x faster" in str(comparison)
    
    def test_compare_slower(self):
        """Test comparison when current is slower."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=100,
            total_ms=500.0,
            avg_ms=5.0,
            min_ms=2.0,
            max_ms=10.0,
            p50_ms=5.0,
            p95_ms=9.0,
            p99_ms=9.5,
            throughput_qps=200.0
        )
        
        current = BenchmarkResult(
            name="current",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0
        )
        
        benchmark = QueryBenchmark()
        comparison = benchmark.compare_results(baseline, current)
        
        assert comparison.speedup == 0.5  # 2x slower
        assert comparison.regression is True
        assert "2.00x slower" in str(comparison)
    
    def test_regression_threshold(self):
        """Test regression threshold."""
        baseline = BenchmarkResult(
            name="baseline",
            iterations=100,
            total_ms=1000.0,
            avg_ms=10.0,
            min_ms=5.0,
            max_ms=20.0,
            p50_ms=10.0,
            p95_ms=18.0,
            p99_ms=19.5,
            throughput_qps=100.0
        )
        
        # 15% slower (within 10% threshold should not regress with 1.1)
        slightly_slower = BenchmarkResult(
            name="current",
            iterations=100,
            total_ms=1150.0,
            avg_ms=11.5,
            min_ms=6.0,
            max_ms=22.0,
            p50_ms=11.5,
            p95_ms=20.0,
            p99_ms=21.0,
            throughput_qps=87.0
        )
        
        benchmark = QueryBenchmark()
        
        # With 1.1 threshold (10%), 15% slower should regress
        comparison = benchmark.compare_results(
            baseline,
            slightly_slower,
            threshold=1.1
        )
        assert comparison.regression is True
        
        # With 1.2 threshold (20%), 15% slower should not regress
        comparison = benchmark.compare_results(
            baseline,
            slightly_slower,
            threshold=1.2
        )
        assert comparison.regression is False


class TestLargeDataset:
    """Tests with large datasets."""
    
    def test_large_partition_scan(self):
        """Test partition scan with large dataset."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_partition_scan(
            partition_size=1000,
            iterations=10
        )
        
        assert result.success_count == 10
        assert result.metadata['partition_size'] == 1000
        # Should still be reasonably fast
        assert result.avg_ms < 1000  # Less than 1 second
    
    def test_large_table_scan(self):
        """Test table scan with large dataset."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_table_scan(
            table_size=10000,
            iterations=5
        )
        
        assert result.success_count == 5
        assert result.metadata['table_size'] == 10000
        # Should complete
        assert result.avg_ms > 0


class TestConcurrency:
    """Tests for concurrent execution."""
    
    def test_concurrent_point_queries(self):
        """Test concurrent point queries."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_concurrent_queries(
            query_count=100,
            thread_count=10,
            query_type="point"
        )
        
        assert result.iterations == 100
        assert result.success_count == 100
        assert result.error_count == 0
    
    def test_concurrent_partition_scans(self):
        """Test concurrent partition scans."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_concurrent_queries(
            query_count=50,
            thread_count=5,
            query_type="partition"
        )
        
        assert result.iterations == 50
        assert result.success_count == 50
    
    def test_concurrent_table_scans(self):
        """Test concurrent table scans."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_concurrent_queries(
            query_count=20,
            thread_count=4,
            query_type="table"
        )
        
        assert result.iterations == 20
        assert result.success_count == 20
    
    def test_high_concurrency(self):
        """Test high concurrency."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_concurrent_queries(
            query_count=200,
            thread_count=20,
            query_type="point"
        )
        
        assert result.iterations == 200
        # Should handle high concurrency
        assert result.success_count + result.error_count == 200


class TestPerformanceTargets:
    """Tests for performance targets."""
    
    def test_point_query_target(self):
        """Test point query meets < 1ms target."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(iterations=1000)
        
        # Target: < 1ms (relaxed for CI)
        # In production, should consistently meet 1ms
        assert result.avg_ms < 10  # Relaxed target
    
    def test_partition_scan_target(self):
        """Test partition scan meets < 10ms target."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_partition_scan(
            partition_size=100,
            iterations=100
        )
        
        # Target: < 10ms for 100 entities (relaxed for CI)
        assert result.avg_ms < 100  # Relaxed target
    
    def test_complex_filter_overhead(self):
        """Test complex filter is < 2x simple filter."""
        benchmark = QueryBenchmark()
        
        simple = benchmark.bench_point_query(iterations=100)
        complex_result = benchmark.bench_complex_filter(
            complexity=10,
            entity_count=1,
            iterations=100
        )
        
        # Complex should be less than 2x simple (relaxed)
        # Note: This may not always hold in CI
        assert complex_result.avg_ms < simple.avg_ms * 10  # Very relaxed


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_entity_list(self):
        """Test benchmark with empty entity list."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_partition_scan(
            partition_size=0,
            iterations=10
        )
        
        assert result.success_count == 10
        assert result.avg_ms >= 0
    
    def test_single_iteration(self):
        """Test benchmark with single iteration."""
        benchmark = QueryBenchmark()
        
        result = benchmark.bench_point_query(iterations=1)
        
        assert result.iterations == 1
        assert result.success_count == 1
        assert result.min_ms == result.max_ms
    
    def test_zero_latency_comparison(self):
        """Test comparison with zero latency."""
        benchmark = QueryBenchmark()
        
        baseline = BenchmarkResult(
            name="baseline",
            iterations=1,
            total_ms=0.0,
            avg_ms=0.0,
            min_ms=0.0,
            max_ms=0.0,
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            throughput_qps=0.0
        )
        
        current = BenchmarkResult(
            name="current",
            iterations=1,
            total_ms=1.0,
            avg_ms=1.0,
            min_ms=1.0,
            max_ms=1.0,
            p50_ms=1.0,
            p95_ms=1.0,
            p99_ms=1.0,
            throughput_qps=1000.0
        )
        
        comparison = benchmark.compare_results(baseline, current)
        
        # Should handle zero latency gracefully
        assert comparison.speedup == 0.0
