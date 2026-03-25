# ──────────────────────────────────────────────────────────────
# E2B Sandbox Template Configuration
# ──────────────────────────────────────────────────────────────
# Central config for sandbox resource limits.
#
# The e2b.Dockerfile uses multi-stage builds (falkordb, codex,
# obfuscator, main) which the V2 Python SDK cannot parse.
# We therefore use the E2B CLI (`e2b template build`) via the
# build_prod.py / build_dev.py scripts, passing these values
# as --cpu-count and --memory-mb flags.
#
# CPU and RAM are set at TEMPLATE BUILD TIME — every sandbox
# created from this template inherits these resource limits.
# ──────────────────────────────────────────────────────────────

# Resource configuration — change these values to adjust ALL sandboxes
SANDBOX_CPU_COUNT = 4       # Number of vCPUs (was 2 by default)
SANDBOX_MEMORY_MB = 2048    # RAM in megabytes (was 1024 by default)

# Start command (must match e2b.toml)
SANDBOX_START_CMD = "bash /app/start-services.sh"
