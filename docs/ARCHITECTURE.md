# Architecture Deep Dive

## System Architecture

### High-Level Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster (Minikube)                  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   kube-system Namespace                   │    │
│  │                                                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │    │
│  │  │  GreedyLB   │  │  RefineLB   │  │    Pattern     │  │    │
│  │  │  Scheduler  │  │  Scheduler  │  │   Detector     │  │    │
│  │  │             │  │             │  │                │  │    │
│  │  │  Pod (1x)   │  │  Pod (1x)   │  │   Pod (1x)     │  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬───────┘  │    │
│  │         │                 │                   │          │    │
│  └─────────┼─────────────────┼───────────────────┼──────────┘    │
│            │                 │                   │               │
│            ▼                 ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Kubernetes API Server                       │    │
│  │  • Watch for unscheduled pods                           │    │
│  │  • Read node metrics                                    │    │
│  │  • Update deployment schedulerName                      │    │
│  │  • Bind pods to nodes                                   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Worker Nodes (3x)                       │    │
│  │                                                          │    │
│  │  Node-1          Node-2          Node-3                 │    │
│  │  ┌─────┐         ┌─────┐         ┌─────┐                │    │
│  │  │ Pod │         │ Pod │         │ Pod │                │    │
│  │  └─────┘         └─────┘         └─────┘                │    │
│  │  ┌─────┐         ┌─────┐         ┌─────┐                │    │
│  │  │ Pod │         │ Pod │         │ Pod │                │    │
│  │  └─────┘         └─────┘         └─────┘                │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. GreedyLB Scheduler

**File**: `schedulers/greedylb/scheduler.py`

**Purpose**: Fast, greedy scheduling for stable/linear workloads

**Algorithm Flow**:
```python
1. Watch for pods with schedulerName="greedylb-scheduler"
2. Get all schedulable nodes (Ready, not cordoned)
3. For each node:
   - Calculate available CPU and memory
   - Score = (CPU_available * 0.7) + (Memory_available * 0.3)
4. Select node with highest score (greedy)
5. Bind pod to selected node
```

**Complexity**: O(n) where n = number of nodes

**Scoring Formula**:
```
Node_Score = (CPU_available / CPU_total) × 70 + (Memory_available / Memory_total) × 30
```

**Performance Characteristics**:
- **Scheduling Time**: 50-100ms per pod
- **Memory Usage**: ~128MB
- **CPU Usage**: ~100m
- **Best For**: Clusters with predictable, steady workload growth

**Trade-offs**:
- ✅ Fast scheduling decisions
- ✅ Low resource overhead
- ❌ May create hotspots under heavy load
- ❌ Doesn't optimize for cluster-wide balance

---

### 2. RefineLB Scheduler

**File**: `schedulers/refinelb/scheduler.py`

**Purpose**: Advanced load balancing for exponential workloads

**Algorithm Flow**:
```python
1. Watch for pods with schedulerName="refinelb-scheduler"
2. Get all schedulable nodes
3. Collect resource usage for ALL nodes
4. For each node, calculate multi-factor score:
   a. Available Resources Score (40%)
   b. Balance Score (30%)
   c. Pod Density Score (20%)
   d. Target Utilization Score (10%)
5. Select node with highest combined score
6. Bind pod to selected node
```

**Complexity**: O(n) where n = number of nodes (but with more computation per node)

**Multi-Factor Scoring**:

```python
# Factor 1: Available Resources (40%)
resources_score = (
    (cpu_available / cpu_total) * 0.5 +
    (memory_available / memory_total) * 0.5
) * 40

# Factor 2: Balance Score (30%)
# Prefer nodes closer to cluster average utilization
cpu_balance = 100 - abs(new_cpu_util - avg_cpu_util)
mem_balance = 100 - abs(new_mem_util - avg_mem_util)
balance_score = (cpu_balance * 0.5 + mem_balance * 0.5) * 0.3

# Factor 3: Pod Density (20%)
# Prefer nodes with fewer pods (better spreading)
pod_density = (1 - (pod_count / 110)) * 20

# Factor 4: Target Utilization (10%)
# Aim for 60-70% utilization sweet spot
target_util = 65
cpu_target_score = 100 - abs(new_cpu_util - target_util)
mem_target_score = 100 - abs(new_mem_util - target_util)
target_score = (cpu_target_score * 0.5 + mem_target_score * 0.5) * 0.1

# Total Score
total_score = resources_score + balance_score + pod_density + target_score
```

**Performance Characteristics**:
- **Scheduling Time**: 100-200ms per pod
- **Memory Usage**: ~200MB
- **CPU Usage**: ~200m
- **Best For**: Large clusters, burst traffic, exponential growth

**Trade-offs**:
- ✅ Optimal resource distribution
- ✅ Prevents node hotspots
- ✅ Better long-term cluster health
- ❌ Slower scheduling decisions
- ❌ Higher resource overhead

---

### 3. Pattern Detector

**File**: `monitoring/pattern_detector.py`

**Purpose**: Monitors workload patterns and switches schedulers

**Detection Algorithm**:

```python
# Monitoring Loop (every 10 seconds)
while True:
    # 1. Get current active pod count
    current_pods = count_active_pods()

    # 2. Store in history (sliding window of 6 samples)
    history.append(current_pods)

    # 3. Calculate growth rate
    if len(history) >= 2:
        oldest = history[0]
        newest = history[-1]
        growth_rate = ((newest - oldest) / oldest) * 100

    # 4. Classify pattern
    if abs(growth_rate) < 10:
        pattern = STABLE
    elif abs(growth_rate) < 30:
        pattern = LINEAR
    else:
        pattern = EXPONENTIAL

    # 5. Determine optimal scheduler
    if pattern in [STABLE, LINEAR]:
        optimal = "greedylb-scheduler"
    else:
        optimal = "refinelb-scheduler"

    # 6. Switch if needed
    if optimal != current_scheduler:
        update_all_deployments(optimal)
        current_scheduler = optimal

    sleep(10)
```

**Pattern Classification**:

```
Growth Rate         Pattern         Scheduler
-----------         -------         ---------
< 10%              Stable          GreedyLB
10% - 30%          Linear          GreedyLB
≥ 30%              Exponential     RefineLB
```

**State Machine**:

```
                    < 30% growth
    ┌──────────────────────────────────┐
    │                                  │
    ▼                                  │
┌─────────┐                      ┌─────────┐
│ GreedyLB│                      │RefineLB │
│ Active  │                      │ Active  │
└─────────┘                      └─────────┘
    │                                  ▲
    │                                  │
    └──────────────────────────────────┘
                ≥ 30% growth
```

**Performance Characteristics**:
- **Detection Latency**: 10-60 seconds (depends on history window)
- **Memory Usage**: ~128MB
- **CPU Usage**: ~50m
- **Monitoring Overhead**: Negligible

---

## Data Flow

### Pod Scheduling Flow

```
1. User creates Deployment
   ├─> spec.template.spec.schedulerName: "greedylb-scheduler"
   └─> spec.replicas: 5

2. Kubernetes creates Pods
   ├─> Pod-1 (Pending, schedulerName: greedylb-scheduler)
   ├─> Pod-2 (Pending, schedulerName: greedylb-scheduler)
   └─> Pod-3 (Pending, schedulerName: greedylb-scheduler)

3. GreedyLB Scheduler watches API
   └─> Detects unscheduled pods with matching schedulerName

4. For each pod:
   ├─> Get schedulable nodes
   ├─> Calculate scores
   ├─> Select best node
   └─> Bind pod to node

5. Kubelet on node
   └─> Pulls image and starts container

6. Pod transitions: Pending → Running
```

### Pattern Detection Flow

```
1. Pattern Detector monitors (every 10s)
   └─> Query API: list_pod_for_all_namespaces()

2. Filter active pods
   ├─> Exclude: kube-system, kube-public
   ├─> Include: Running, Pending
   └─> Count: N pods

3. Add to history
   └─> history = [5, 7, 10, 15, 22, 35]  # Last 6 samples

4. Calculate growth rate
   └─> (35 - 5) / 5 * 100 = +600% (very high!)

5. Classify pattern
   └─> +600% > 30% → EXPONENTIAL

6. Determine optimal scheduler
   └─> EXPONENTIAL → refinelb-scheduler

7. Check if switch needed
   ├─> current: greedylb-scheduler
   ├─> optimal: refinelb-scheduler
   └─> Switch needed!

8. Update all deployments
   └─> PATCH /apis/apps/v1/namespaces/{ns}/deployments/{name}
       spec.template.spec.schedulerName = "refinelb-scheduler"

9. New pods use RefineLB
   └─> Future replicas scheduled with RefineLB
```

---

## RBAC and Security

### Scheduler Permissions

**ServiceAccount**: `custom-scheduler`

**Required Permissions**:
- `pods`: get, list, watch (find unscheduled pods)
- `bindings`: create (bind pods to nodes)
- `nodes`: get, list, watch (query node resources)
- `pods/status`: patch, update (update pod status)
- `events`: create (log scheduling events)

### Monitor Permissions

**ServiceAccount**: `pattern-detector`

**Required Permissions**:
- `pods`: get, list, watch (monitor pod count)
- `nodes`: get, list, watch (cluster info)
- `deployments`: get, list, watch, patch, update (switch schedulers)
- `events`: create (log pattern changes)

---

## Scalability Considerations

### Current Implementation
- **Cluster Size**: 3-10 nodes
- **Concurrent Pods**: Up to 100 pods
- **Scheduling Throughput**:
  - GreedyLB: ~20 pods/second
  - RefineLB: ~10 pods/second

### Scaling Limits
- **Max Nodes**: 100 (single scheduler instance)
- **Max Pods**: 1000 (before scheduling latency increases)

### Improvements for Large Scale
1. **Scheduler HA**: Run multiple scheduler replicas with leader election
2. **Caching**: Cache node metrics (reduce API calls)
3. **Batch Scheduling**: Process multiple pods together
4. **Node Pooling**: Pre-filter node candidates

---

## Failure Modes and Recovery

### Scheduler Failure
- **Detection**: Kubernetes readiness/liveness probes
- **Recovery**: Automatic pod restart
- **Impact**: Pods stay pending until scheduler recovers (typically < 30s)

### Monitor Failure
- **Detection**: Health checks
- **Recovery**: Automatic restart
- **Impact**: No scheduler switching until recovery (schedulers continue running)

### API Server Failure
- **Detection**: Connection timeout
- **Recovery**: Automatic reconnection with exponential backoff
- **Impact**: All scheduling pauses

### Node Failure
- **Detection**: Node NotReady status
- **Recovery**: Kubernetes reschedules pods
- **Impact**: Pods rescheduled by active scheduler

---

## Performance Tuning

### GreedyLB Tuning
```python
# Adjust scoring weights
CPU_WEIGHT = 0.7      # Increase for CPU-heavy workloads
MEMORY_WEIGHT = 0.3   # Increase for memory-heavy workloads
```

### RefineLB Tuning
```python
# Adjust scoring factors
RESOURCES_WEIGHT = 0.4   # Available resources importance
BALANCE_WEIGHT = 0.3     # Cluster balance importance
DENSITY_WEIGHT = 0.2     # Pod spreading importance
TARGET_WEIGHT = 0.1      # Target utilization importance

# Adjust target utilization
TARGET_UTILIZATION = 65  # Aim for 65% node utilization
```

### Pattern Detector Tuning
```python
MONITOR_INTERVAL = 10    # Faster detection (higher CPU)
HISTORY_WINDOW = 6       # Larger window (more stable)
STABLE_THRESHOLD = 10    # Lower = more sensitive
LINEAR_THRESHOLD = 30    # Higher = less switching
```

---

## Future Enhancements

1. **Machine Learning Integration**: Predict workload patterns before they occur
2. **Custom Metrics**: Use Prometheus metrics for advanced detection
3. **Cost Optimization**: Consider node pricing in scheduling decisions
4. **Multi-Zone Awareness**: Spread pods across availability zones
5. **Application-Aware Scheduling**: Custom scheduling rules per app type
6. **Historical Analysis**: Learn from past patterns to improve detection

---

**Document Version**: 1.0
**Last Updated**: November 24, 2025
