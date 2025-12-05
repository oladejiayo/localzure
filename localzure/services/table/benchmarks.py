"""
Performance Benchmarking Suite for OData Query Engine.

This module provides comprehensive benchmarking tools to measure and validate
query engine performance against Azure Table Storage targets.

Features:
- Query type benchmarking (point, partition scan, table scan)
- Memory profiling and leak detection
- Concurrent query handling
- Query plan caching effectiveness
- Performance comparison utilities
- Regression detection

Performance Targets (from Azure Table Storage):
- Point Query: < 1ms @ 10k qps
- Partition Scan (100): < 10ms @ 1k qps
- Table Scan (1k): < 100ms @ 100 qps
- Complex Filter: < 2x simple @ 500 qps

Example:
    >>> benchmark = QueryBenchmark()
    >>> results = benchmark.bench_point_query(iterations=10000)
    >>> print(f"Avg: {results.avg_ms:.2f}ms, p95: {results.p95_ms:.2f}ms")

Author: LocalZure Team
Version: 1.0.0
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import time
import gc
import tracemalloc
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .lexer import ODataLexer
from .parser import ODataParser
from .evaluator import QueryEvaluator


@dataclass
class BenchmarkResult:
    """
    Results from a benchmark run.
    
    Attributes:
        name: Benchmark name
        iterations: Number of iterations
        total_ms: Total execution time
        avg_ms: Average latency
        min_ms: Minimum latency
        max_ms: Maximum latency
        p50_ms: 50th percentile (median)
        p95_ms: 95th percentile
        p99_ms: 99th percentile
        throughput_qps: Queries per second
        memory_peak_mb: Peak memory usage
        memory_leaked_mb: Memory leaked (if detected)
        success_count: Successful queries
        error_count: Failed queries
        metadata: Additional benchmark-specific data
    """
    name: str
    iterations: int
    total_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_qps: float
    memory_peak_mb: float = 0.0
    memory_leaked_mb: float = 0.0
    success_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def meets_target(self, target_ms: float) -> bool:
        """Check if average latency meets target."""
        return self.avg_ms <= target_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'iterations': self.iterations,
            'latency': {
                'total_ms': round(self.total_ms, 2),
                'avg_ms': round(self.avg_ms, 3),
                'min_ms': round(self.min_ms, 3),
                'max_ms': round(self.max_ms, 3),
                'p50_ms': round(self.p50_ms, 3),
                'p95_ms': round(self.p95_ms, 3),
                'p99_ms': round(self.p99_ms, 3),
            },
            'throughput_qps': round(self.throughput_qps, 1),
            'memory': {
                'peak_mb': round(self.memory_peak_mb, 2),
                'leaked_mb': round(self.memory_leaked_mb, 2),
            },
            'success_count': self.success_count,
            'error_count': self.error_count,
            'metadata': self.metadata,
        }


@dataclass
class ComparisonResult:
    """
    Performance comparison between two benchmarks.
    
    Attributes:
        baseline: Baseline benchmark name
        current: Current benchmark name
        speedup: Speedup factor (baseline/current)
        regression: True if performance regressed
        threshold: Regression threshold (e.g., 1.1 = 10% slower)
    """
    baseline: BenchmarkResult
    current: BenchmarkResult
    speedup: float
    regression: bool
    threshold: float = 1.1
    
    def __str__(self) -> str:
        if self.speedup > 1.0:
            return f"{self.speedup:.2f}x faster than baseline"
        elif self.speedup < 1.0:
            return f"{1/self.speedup:.2f}x slower than baseline"
        else:
            return "Same performance as baseline"


class QueryBenchmark:
    """
    Comprehensive query performance benchmarking.
    
    Provides methods to benchmark different query types and measure
    performance characteristics including latency, throughput, and
    memory usage.
    
    Thread Safety:
        QueryBenchmark is thread-safe for concurrent benchmarking.
    """
    
    def __init__(self):
        """Initialize benchmark suite."""
        self.results: List[BenchmarkResult] = []
        self._lock = threading.Lock()
    
    def bench_point_query(
        self,
        iterations: int = 10000,
        profile_memory: bool = False
    ) -> BenchmarkResult:
        """
        Benchmark point query performance.
        
        Point queries filter on both PartitionKey and RowKey, resulting
        in O(1) lookups. Target: < 1ms average latency.
        
        Args:
            iterations: Number of queries to execute
            profile_memory: Enable memory profiling
            
        Returns:
            Benchmark results with latency and throughput metrics
        """
        query = "PartitionKey eq 'product' and RowKey eq 'item123'"
        entity = {
            'PartitionKey': 'product',
            'RowKey': 'item123',
            'Price': 99.99,
            'Stock': 100
        }
        
        return self._run_benchmark(
            name="point_query",
            query=query,
            entities=[entity],
            iterations=iterations,
            profile_memory=profile_memory
        )
    
    def bench_partition_scan(
        self,
        partition_size: int = 100,
        iterations: int = 1000,
        profile_memory: bool = False
    ) -> BenchmarkResult:
        """
        Benchmark partition scan performance.
        
        Partition scans filter on PartitionKey with additional filters,
        resulting in O(n) scans within a partition. Target: < 10ms for 100 entities.
        
        Args:
            partition_size: Number of entities in partition
            iterations: Number of queries to execute
            profile_memory: Enable memory profiling
            
        Returns:
            Benchmark results with latency and throughput metrics
        """
        query = "PartitionKey eq 'product' and Price gt 50"
        
        # Create partition with entities
        entities = [
            {
                'PartitionKey': 'product',
                'RowKey': f'item{i:04d}',
                'Price': float(i),
                'Stock': i * 10
            }
            for i in range(partition_size)
        ]
        
        return self._run_benchmark(
            name="partition_scan",
            query=query,
            entities=entities,
            iterations=iterations,
            profile_memory=profile_memory,
            metadata={'partition_size': partition_size}
        )
    
    def bench_table_scan(
        self,
        table_size: int = 10000,
        iterations: int = 100,
        profile_memory: bool = False
    ) -> BenchmarkResult:
        """
        Benchmark table scan performance.
        
        Table scans filter without PartitionKey, requiring full table scan.
        Target: < 100ms for 1000 entities.
        
        Args:
            table_size: Number of entities in table
            iterations: Number of queries to execute
            profile_memory: Enable memory profiling
            
        Returns:
            Benchmark results with latency and throughput metrics
        """
        query = "Price gt 50 and Stock lt 100"
        
        # Create table with multiple partitions
        entities = []
        for partition_idx in range(table_size // 10):
            for row_idx in range(10):
                entities.append({
                    'PartitionKey': f'partition{partition_idx:04d}',
                    'RowKey': f'row{row_idx:04d}',
                    'Price': float(partition_idx * 10 + row_idx),
                    'Stock': (partition_idx * 10 + row_idx) % 200
                })
        
        return self._run_benchmark(
            name="table_scan",
            query=query,
            entities=entities,
            iterations=iterations,
            profile_memory=profile_memory,
            metadata={'table_size': table_size}
        )
    
    def bench_complex_filter(
        self,
        complexity: int = 10,
        entity_count: int = 100,
        iterations: int = 1000,
        profile_memory: bool = False
    ) -> BenchmarkResult:
        """
        Benchmark complex filter expression performance.
        
        Complex filters include multiple AND/OR clauses, function calls,
        and nested expressions. Target: < 2x simple filter latency.
        
        Args:
            complexity: Number of filter clauses
            entity_count: Number of entities to filter
            iterations: Number of queries to execute
            profile_memory: Enable memory profiling
            
        Returns:
            Benchmark results with latency and throughput metrics
        """
        # Build complex query with multiple clauses
        clauses = ["Price gt 50"]
        for i in range(1, complexity):
            if i % 3 == 0:
                clauses.append(f"Stock gt {i * 10}")
            elif i % 3 == 1:
                clauses.append(f"Price lt {i * 100}")
            else:
                clauses.append("Active eq true")
        
        query = " and ".join(clauses)
        
        # Create entities
        entities = [
            {
                'PartitionKey': 'product',
                'RowKey': f'item{i:04d}',
                'Price': float(i * 10),
                'Stock': i * 5,
                'Active': i % 2 == 0
            }
            for i in range(entity_count)
        ]
        
        return self._run_benchmark(
            name="complex_filter",
            query=query,
            entities=entities,
            iterations=iterations,
            profile_memory=profile_memory,
            metadata={'complexity': complexity, 'entity_count': entity_count}
        )
    
    def bench_function_calls(
        self,
        function_name: str = "startswith",
        entity_count: int = 100,
        iterations: int = 1000,
        profile_memory: bool = False
    ) -> BenchmarkResult:
        """
        Benchmark function call performance.
        
        Tests performance of OData functions like startswith, contains, etc.
        
        Args:
            function_name: Function to benchmark
            entity_count: Number of entities to filter
            iterations: Number of queries to execute
            profile_memory: Enable memory profiling
            
        Returns:
            Benchmark results
        """
        query = f"{function_name}(Name, 'test')"
        
        entities = [
            {
                'PartitionKey': 'product',
                'RowKey': f'item{i:04d}',
                'Name': f'test-product-{i}',
                'Value': i
            }
            for i in range(entity_count)
        ]
        
        return self._run_benchmark(
            name=f"function_{function_name}",
            query=query,
            entities=entities,
            iterations=iterations,
            profile_memory=profile_memory,
            metadata={'function': function_name}
        )
    
    def bench_concurrent_queries(
        self,
        query_count: int = 1000,
        thread_count: int = 10,
        query_type: str = "point"
    ) -> BenchmarkResult:
        """
        Benchmark concurrent query handling.
        
        Tests thread safety and concurrent performance of the query engine.
        
        Args:
            query_count: Total number of queries
            thread_count: Number of concurrent threads
            query_type: Type of query ("point", "partition", or "table")
            
        Returns:
            Benchmark results including concurrency metrics
        """
        start_time = time.perf_counter()
        
        # Prepare query and entities based on type
        if query_type == "point":
            query = "PartitionKey eq 'product' and RowKey eq 'item123'"
            entities = [{'PartitionKey': 'product', 'RowKey': 'item123', 'Value': 1}]
        elif query_type == "partition":
            query = "PartitionKey eq 'product' and Price gt 50"
            entities = [
                {'PartitionKey': 'product', 'RowKey': f'item{i}', 'Price': float(i)}
                for i in range(100)
            ]
        else:  # table
            query = "Price gt 50"
            entities = [
                {'PartitionKey': f'p{i//10}', 'RowKey': f'r{i}', 'Price': float(i)}
                for i in range(100)
            ]
        
        # Parse query once
        lexer = ODataLexer(query)
        tokens = lexer.tokenize()
        parser = ODataParser(tokens)
        ast = parser.parse()
        
        latencies = []
        success = 0
        errors = 0
        lock = threading.Lock()
        
        def execute_query():
            nonlocal success, errors
            try:
                query_start = time.perf_counter()
                evaluator = QueryEvaluator()
                
                # Execute filter
                for entity in entities:
                    evaluator.evaluate(ast, entity)
                
                query_end = time.perf_counter()
                latency = (query_end - query_start) * 1000
                
                with lock:
                    latencies.append(latency)
                    success += 1
            except Exception:
                with lock:
                    errors += 1
        
        # Execute queries concurrently
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(execute_query) for _ in range(query_count)]
            for future in as_completed(futures):
                future.result()
        
        end_time = time.perf_counter()
        total_ms = (end_time - start_time) * 1000
        
        # Calculate statistics
        if latencies:
            latencies.sort()
            avg_ms = statistics.mean(latencies)
            min_ms = latencies[0]
            max_ms = latencies[-1]
            p50_ms = latencies[len(latencies) // 2]
            p95_ms = latencies[int(len(latencies) * 0.95)]
            p99_ms = latencies[int(len(latencies) * 0.99)]
        else:
            avg_ms = min_ms = max_ms = p50_ms = p95_ms = p99_ms = 0.0
        
        throughput_qps = (query_count / total_ms) * 1000 if total_ms > 0 else 0
        
        result = BenchmarkResult(
            name=f"concurrent_{query_type}",
            iterations=query_count,
            total_ms=total_ms,
            avg_ms=avg_ms,
            min_ms=min_ms,
            max_ms=max_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            throughput_qps=throughput_qps,
            success_count=success,
            error_count=errors,
            metadata={'thread_count': thread_count, 'query_type': query_type}
        )
        
        with self._lock:
            self.results.append(result)
        
        return result
    
    def bench_cache_effectiveness(
        self,
        unique_queries: int = 100,
        iterations_per_query: int = 100
    ) -> BenchmarkResult:
        """
        Benchmark query plan caching effectiveness.
        
        Measures cache hit rate and performance improvement from caching.
        
        Args:
            unique_queries: Number of unique query patterns
            iterations_per_query: Repetitions per query
            
        Returns:
            Benchmark results with cache metrics
        """
        queries = [
            f"Price gt {i} and Stock lt {i * 10}"
            for i in range(unique_queries)
        ]
        
        entity = {'PartitionKey': 'p1', 'RowKey': 'r1', 'Price': 50.0, 'Stock': 500}
        
        start_time = time.perf_counter()
        latencies = []
        
        # Execute queries multiple times (cache should help on repeats)
        for _ in range(iterations_per_query):
            for query in queries:
                query_start = time.perf_counter()
                
                lexer = ODataLexer(query)
                tokens = lexer.tokenize()
                parser = ODataParser(tokens)
                ast = parser.parse()
                evaluator = QueryEvaluator()
                evaluator.evaluate(ast, entity)
                
                query_end = time.perf_counter()
                latencies.append((query_end - query_start) * 1000)
        
        end_time = time.perf_counter()
        total_ms = (end_time - start_time) * 1000
        total_iterations = unique_queries * iterations_per_query
        
        # Calculate statistics
        latencies.sort()
        avg_ms = statistics.mean(latencies)
        
        result = BenchmarkResult(
            name="cache_effectiveness",
            iterations=total_iterations,
            total_ms=total_ms,
            avg_ms=avg_ms,
            min_ms=latencies[0],
            max_ms=latencies[-1],
            p50_ms=latencies[len(latencies) // 2],
            p95_ms=latencies[int(len(latencies) * 0.95)],
            p99_ms=latencies[int(len(latencies) * 0.99)],
            throughput_qps=(total_iterations / total_ms) * 1000,
            success_count=total_iterations,
            error_count=0,
            metadata={
                'unique_queries': unique_queries,
                'iterations_per_query': iterations_per_query
            }
        )
        
        with self._lock:
            self.results.append(result)
        
        return result
    
    def _run_benchmark(
        self,
        name: str,
        query: str,
        entities: List[Dict[str, Any]],
        iterations: int,
        profile_memory: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BenchmarkResult:
        """
        Internal method to run a benchmark.
        
        Args:
            name: Benchmark name
            query: OData query expression
            entities: Entity list
            iterations: Number of iterations
            profile_memory: Enable memory profiling
            metadata: Additional metadata
            
        Returns:
            Benchmark results
        """
        # Force garbage collection before benchmark
        gc.collect()
        
        # Start memory profiling if requested
        if profile_memory:
            tracemalloc.start()
            mem_before = tracemalloc.get_traced_memory()[0]
        
        # Parse query once (simulate caching)
        lexer = ODataLexer(query)
        tokens = lexer.tokenize()
        parser = ODataParser(tokens)
        ast = parser.parse()
        
        # Warm up
        evaluator = QueryEvaluator()
        for entity in entities[:min(10, len(entities))]:
            evaluator.evaluate(ast, entity)
        
        # Run benchmark
        start_time = time.perf_counter()
        latencies = []
        success = 0
        errors = 0
        
        for _ in range(iterations):
            query_start = time.perf_counter()
            
            try:
                evaluator = QueryEvaluator()
                matches = 0
                for entity in entities:
                    if evaluator.evaluate(ast, entity):
                        matches += 1
                
                query_end = time.perf_counter()
                latencies.append((query_end - query_start) * 1000)
                success += 1
                
            except Exception:
                errors += 1
        
        end_time = time.perf_counter()
        total_ms = (end_time - start_time) * 1000
        
        # Memory profiling
        memory_peak_mb = 0.0
        memory_leaked_mb = 0.0
        if profile_memory:
            mem_after, mem_peak = tracemalloc.get_traced_memory()
            memory_peak_mb = mem_peak / (1024 * 1024)
            memory_leaked_mb = (mem_after - mem_before) / (1024 * 1024)
            tracemalloc.stop()
        
        # Calculate statistics
        if latencies:
            latencies.sort()
            avg_ms = statistics.mean(latencies)
            min_ms = latencies[0]
            max_ms = latencies[-1]
            p50_ms = latencies[len(latencies) // 2]
            p95_ms = latencies[int(len(latencies) * 0.95)]
            p99_ms = latencies[int(len(latencies) * 0.99)]
        else:
            avg_ms = min_ms = max_ms = p50_ms = p95_ms = p99_ms = 0.0
        
        throughput_qps = (success / total_ms) * 1000 if total_ms > 0 else 0
        
        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_ms=total_ms,
            avg_ms=avg_ms,
            min_ms=min_ms,
            max_ms=max_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            throughput_qps=throughput_qps,
            memory_peak_mb=memory_peak_mb,
            memory_leaked_mb=memory_leaked_mb,
            success_count=success,
            error_count=errors,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.results.append(result)
        
        return result
    
    def compare_results(
        self,
        baseline: BenchmarkResult,
        current: BenchmarkResult,
        threshold: float = 1.1
    ) -> ComparisonResult:
        """
        Compare two benchmark results.
        
        Args:
            baseline: Baseline benchmark
            current: Current benchmark
            threshold: Regression threshold (e.g., 1.1 = 10% slower)
            
        Returns:
            Comparison result with speedup and regression info
        """
        speedup = baseline.avg_ms / current.avg_ms if current.avg_ms > 0 else 0.0
        regression = speedup < (1.0 / threshold)
        
        return ComparisonResult(
            baseline=baseline,
            current=current,
            speedup=speedup,
            regression=regression,
            threshold=threshold
        )
    
    def get_all_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        with self._lock:
            return list(self.results)
    
    def reset(self):
        """Reset all benchmark results."""
        with self._lock:
            self.results.clear()
