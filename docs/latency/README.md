# Latency Documentation Suite

This directory contains comprehensive documentation on latency analysis and optimization for the agents-backend chat system.

## Documents

| Document | Description |
|----------|-------------|
| [01-backend-chat-mode.md](01-backend-chat-mode.md) | SSE streaming latency in chat mode |
| [02-backend-agent-mode.md](02-backend-agent-mode.md) | Socket.IO latency in agent mode with sandbox |
| [03-frontend.md](03-frontend.md) | React/Redux frontend latency analysis |
| [04-integration.md](04-integration.md) | Integration layer and protocol latency |
| [05-recommendations.md](05-recommendations.md) | Prioritized optimization recommendations |

## Key Findings

### Critical Latency Sources
1. **Sandbox Cold Start**: 30-60s (agent mode only)
2. **Pre-streaming DB Writes**: 100-300ms
3. **Triple Event Emission**: 1-5ms per token
4. **Frontend "THINKING" Animation**: 500-1000ms perceived

### Target Metrics
- Time to First Token (TTFT): < 300ms
- Token Interval: < 50ms
- Total Response (typical): < 5s

## Test Harness

A test harness is available at `tests/test_latency.py`:

```bash
# Run all latency tests
pytest tests/test_latency.py -v

# Run benchmarks
python tests/test_latency.py
```

## Quick Start

1. Read [05-recommendations.md](05-recommendations.md) for prioritized actions
2. Implement Phase 1 quick wins (1-2 days effort)
3. Run test harness to verify improvements
4. Proceed with Phase 2 and 3 as needed
