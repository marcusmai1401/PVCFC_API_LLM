# Health Check System

Comprehensive health monitoring for PVCFC RAG API with Kubernetes-ready probes.

## Overview

The health check system provides deep visibility into the status of all critical dependencies:

- **Weaviate**: Vector database for semantic search
- **OpenSearch**: Full-text search with BM25
- **Redis**: Cache and conversation state
- **File System**: Index directories and artifacts

## Endpoints

### `/healthz` - Legacy Health Check

Simple liveness probe that returns basic application info.

**Response:**
```json
{
  "status": "healthy",
  "app_env": "production",
  "version": "1.0.0",
  "commit_sha": "abc123",
  "uptime_seconds": 86400,
  "uptime_human": "1d 0h 0m 0s",
  "llm_provider": "gemini",
  "llm_provider_ready": true,
  "timestamp": "2024-01-15T12:00:00Z"
}
```

### `/livez` - Liveness Probe

Kubernetes liveness probe to check if the application process is alive.

**Use case:** Kubernetes will restart the pod if this fails.

**Response:**
```json
{
  "status": "healthy",
  "type": "liveness",
  "timestamp": 1705320000.123
}
```

**Always returns 200 OK** unless the process is dead.

### `/readyz` - Readiness Probe

Kubernetes readiness probe with deep checks of all dependencies.

**Use case:** Kubernetes will remove pod from load balancer if not ready.

**Response:**
```json
{
  "status": "healthy",
  "type": "readiness",
  "timestamp": 1705320000.123,
  "check_duration_ms": 145.32,
  "components": [
    {
      "name": "weaviate",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 12.5,
      "metadata": {
        "collection": "pvcfc_chunks",
        "ready": true
      }
    },
    {
      "name": "opensearch",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 23.8,
      "metadata": {
        "index": "rag_chunks",
        "cluster_health": "green"
      }
    },
    {
      "name": "redis",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 5.2,
      "metadata": {
        "total_conversations": 142,
        "ttl_hours": 24
      }
    },
    {
      "name": "filesystem",
      "status": "healthy",
      "message": "All critical paths exist",
      "latency_ms": 1.1,
      "metadata": {
        "checked_paths": 2
      }
    }
  ]
}
```

## Status Levels

### Healthy
All components are functioning normally. Service can handle traffic.

### Degraded
One or more components have issues, but service is still functional.
- **Condition**: Less than 50% of components are unhealthy
- **Action**: Alert on-call, but keep pod in load balancer

### Unhealthy
Majority of components are down. Service cannot handle traffic properly.
- **Condition**: More than 50% of components are unhealthy
- **Action**: Remove from load balancer, alert urgently

## Component Details

### Weaviate Health Check
```python
{
  "name": "weaviate",
  "status": "healthy|degraded|unhealthy",
  "message": "Connected and ready",
  "latency_ms": 12.5,
  "metadata": {
    "collection": "pvcfc_chunks",
    "ready": true
  }
}
```

**Checks:**
- Connection to Weaviate API
- Collection exists and is accessible
- Weaviate is in ready state

**States:**
- `healthy`: Connected and ready
- `degraded`: Disabled in config or not initialized
- `unhealthy`: Connection failed or collection missing

### OpenSearch Health Check
```python
{
  "name": "opensearch",
  "status": "healthy|degraded|unhealthy",
  "message": "Connected and ready",
  "latency_ms": 23.8,
  "metadata": {
    "index": "rag_chunks",
    "cluster_health": "green",
    "version": "2.11.0"
  }
}
```

**Checks:**
- Connection to OpenSearch API
- Index exists
- Cluster health (green/yellow/red)

**States:**
- `healthy`: Connected, index exists, cluster green/yellow
- `degraded`: Disabled in config or not initialized
- `unhealthy`: Connection failed, index missing, or cluster red

### Redis Health Check
```python
{
  "name": "redis",
  "status": "healthy|degraded|unhealthy",
  "message": "Connected and ready",
  "latency_ms": 5.2,
  "metadata": {
    "total_conversations": 142,
    "ttl_hours": 24
  }
}
```

**Checks:**
- Redis PING command
- Count of active conversations

**States:**
- `healthy`: Connected and responsive
- `degraded`: Conversation manager not initialized
- `unhealthy`: Connection failed or PING timeout

### Filesystem Health Check
```python
{
  "name": "filesystem",
  "status": "healthy|degraded|unhealthy",
  "message": "All critical paths exist",
  "latency_ms": 1.1,
  "metadata": {
    "checked_paths": 2
  }
}
```

**Checks:**
- Index directory exists (`index_dir`)
- Artifacts directory exists (`artifacts_dir`)

**States:**
- `healthy`: All paths exist
- `degraded`: One or more paths missing
- `unhealthy`: Filesystem check failed with exception

## Kubernetes Integration

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pvcfc-rag-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pvcfc-rag-api
  template:
    metadata:
      labels:
        app: pvcfc-rag-api
    spec:
      containers:
      - name: api
        image: pvcfc-rag-api:latest
        ports:
        - containerPort: 8000
        
        # Liveness probe: Is the process alive?
        livenessProbe:
          httpGet:
            path: /livez
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        # Readiness probe: Can it serve traffic?
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        
        # Startup probe: For slow startup
        startupProbe:
          httpGet:
            path: /livez
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30  # Allow 150s for startup
```

### Configuration Guidelines

#### Liveness Probe
- **Purpose**: Detect dead/frozen processes
- **Path**: `/livez`
- **Timing**:
  - `initialDelaySeconds: 30` - Wait for app to start
  - `periodSeconds: 10` - Check every 10 seconds
  - `failureThreshold: 3` - Restart after 3 failures (30s)

#### Readiness Probe
- **Purpose**: Detect when service can't handle traffic
- **Path**: `/readyz`
- **Timing**:
  - `initialDelaySeconds: 10` - Check soon after startup
  - `periodSeconds: 5` - Check frequently
  - `failureThreshold: 2` - Remove from LB quickly (10s)

#### Startup Probe
- **Purpose**: Give slow-starting apps more time
- **Path**: `/livez`
- **Timing**:
  - `periodSeconds: 5` - Check every 5 seconds
  - `failureThreshold: 30` - Allow up to 150s for startup

## Monitoring & Alerting

### Prometheus Metrics

The health check system can be integrated with Prometheus:

```python
from prometheus_client import Gauge

# Track component health status
health_status = Gauge(
    'health_status',
    'Component health status (1=healthy, 0.5=degraded, 0=unhealthy)',
    ['component']
)

# Update from health check
for component in result['components']:
    status_value = {
        'healthy': 1.0,
        'degraded': 0.5,
        'unhealthy': 0.0
    }[component['status']]
    
    health_status.labels(component=component['name']).set(status_value)
```

### Alert Rules

```yaml
groups:
  - name: health_checks
    interval: 30s
    rules:
      # Critical: Majority of components unhealthy
      - alert: SystemUnhealthy
        expr: health_status < 0.5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "PVCFC RAG API is unhealthy"
          description: "{{ $labels.component }} is unhealthy"
      
      # Warning: Component degraded
      - alert: ComponentDegraded
        expr: health_status == 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Component is degraded"
          description: "{{ $labels.component }} is degraded"
```

## Development

### Local Testing

```bash
# Check liveness
curl http://localhost:8000/livez

# Check readiness (detailed)
curl http://localhost:8000/readyz | jq
```

### Adding New Components

To add a new component to health checks:

1. **Add health check method** to `HealthChecker`:

```python
async def check_new_component(self) -> ComponentHealth:
    """Check new component health"""
    start = time.time()
    
    try:
        # Your health check logic here
        component = getattr(self.app_state, "new_component", None)
        if not component:
            return ComponentHealth(
                name="new_component",
                status=HealthStatus.DEGRADED,
                message="Not initialized",
            )
        
        # Perform actual check
        is_healthy = component.check()
        latency = (time.time() - start) * 1000
        
        return ComponentHealth(
            name="new_component",
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            message="Connected" if is_healthy else "Failed",
            latency_ms=round(latency, 2),
        )
    
    except Exception as e:
        latency = (time.time() - start) * 1000
        return ComponentHealth(
            name="new_component",
            status=HealthStatus.UNHEALTHY,
            message=f"Check failed: {str(e)[:100]}",
            latency_ms=round(latency, 2),
        )
```

2. **Add to check_all()** method:

```python
checks = await asyncio.gather(
    self.check_weaviate(),
    self.check_opensearch(),
    self.check_redis(),
    self.check_filesystem(),
    self.check_new_component(),  # Add here
    return_exceptions=True,
)
```

3. **Write tests** in `tests/test_health_checker.py`

## Troubleshooting

### Component Shows as Degraded

**Weaviate:**
- Check if `settings.weaviate_enabled` is `True`
- Verify `weaviate_retriever` is initialized in `app.state`

**OpenSearch:**
- Check if `settings.opensearch_enabled` is `True`
- Verify `opensearch_retriever` is initialized in `app.state`

**Redis:**
- Verify `conversation_manager` is initialized in `app.state`

### All Checks Timeout

- Increase `timeoutSeconds` in Kubernetes probes
- Check if components are on slow network
- Review component connection timeouts

### False Positives

- Adjust `failureThreshold` to tolerate temporary issues
- Increase `periodSeconds` to reduce check frequency
- Review component health check logic for flakiness

## Best Practices

1. **Don't restart on transient failures**: Use appropriate `failureThreshold`
2. **Separate liveness and readiness**: Don't mix concerns
3. **Keep checks fast**: All checks should complete in < 3s
4. **Monitor check latency**: High latency indicates problems
5. **Test failure scenarios**: Verify probes work when components fail

## References

- [Kubernetes Liveness, Readiness, Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Health Check Pattern](https://microservices.io/patterns/observability/health-check-api.html)
- [Circuit Breaker Integration](./circuit_breakers.md)
