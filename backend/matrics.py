"""
metrics.py — Custom Prometheus metrics for deployment tracking.
Import and use these in deployment_service.py to record real data.
"""
from prometheus_client import Counter, Histogram, Gauge, Info

# ── Deployment counters ───────────────────────────────────────────────────

deployments_total = Counter(
    'gitops_deployments_total',
    'Total number of deployments triggered',
    ['environment', 'triggered_by']   # labels
)

deployments_success = Counter(
    'gitops_deployments_success_total',
    'Total successful deployments',
    ['environment']
)

deployments_failed = Counter(
    'gitops_deployments_failed_total',
    'Total failed deployments',
    ['environment']
)

# ── Duration histogram ────────────────────────────────────────────────────
# Buckets in seconds: 30s, 1m, 2m, 3m, 5m, 10m, +Inf

deployment_duration = Histogram(
    'gitops_deployment_duration_seconds',
    'Time taken for a full deployment pipeline to complete',
    ['environment', 'status'],
    buckets=[30, 60, 120, 180, 300, 600, float('inf')]
)

# ── Active deployments gauge ─────────────────────────────────────────────
# Goes up when deployment starts, down when it finishes

active_deployments = Gauge(
    'gitops_active_deployments',
    'Number of deployments currently running',
    ['environment']
)

# ── Jenkins build metrics ─────────────────────────────────────────────────

jenkins_builds_triggered = Counter(
    'gitops_jenkins_builds_triggered_total',
    'Total Jenkins builds triggered by this platform',
    ['job_name']
)

jenkins_build_duration = Histogram(
    'gitops_jenkins_build_duration_seconds',
    'Jenkins build duration as reported by Jenkins API',
    ['job_name', 'result'],
    buckets=[30, 60, 120, 180, 300, 600, float('inf')]
)

# ── Platform info ─────────────────────────────────────────────────────────

platform_info = Info(
    'gitops_platform',
    'GitOps platform version information'
)
platform_info.info({'version': '1.0.0', 'environment': 'production'})

