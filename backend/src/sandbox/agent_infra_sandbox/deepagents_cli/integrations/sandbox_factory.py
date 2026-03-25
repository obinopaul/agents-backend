"""Sandbox lifecycle management with context managers."""

import os
import shlex
import string
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from deepagents.backends.protocol import SandboxBackendProtocol

from deepagents_cli.config import console


def _run_sandbox_setup(backend: SandboxBackendProtocol, setup_script_path: str) -> None:
    """Run users setup script in sandbox with env var expansion.

    Args:
        backend: Sandbox backend instance
        setup_script_path: Path to setup script file
    """
    script_path = Path(setup_script_path)
    if not script_path.exists():
        msg = f"Setup script not found: {setup_script_path}"
        raise FileNotFoundError(msg)

    console.print(f"[dim]Running setup script: {setup_script_path}...[/dim]")

    # Read script content
    script_content = script_path.read_text()

    # Expand ${VAR} syntax using local environment
    template = string.Template(script_content)
    expanded_script = template.safe_substitute(os.environ)

    # Execute in sandbox with 5-minute timeout
    result = backend.execute(f"bash -c {shlex.quote(expanded_script)}")

    if result.exit_code != 0:
        console.print(f"[red]❌ Setup script failed (exit {result.exit_code}):[/red]")
        console.print(f"[dim]{result.output}[/dim]")
        msg = "Setup failed - aborting"
        raise RuntimeError(msg)

    console.print("[green]✓ Setup complete[/green]")


@contextmanager
def create_modal_sandbox(
    *, sandbox_id: str | None = None, setup_script_path: str | None = None
) -> Generator[SandboxBackendProtocol, None, None]:
    """Create or connect to Modal sandbox.

    Args:
        sandbox_id: Optional existing sandbox ID to reuse
        setup_script_path: Optional path to setup script to run after sandbox starts

    Yields:
        (ModalBackend, sandbox_id)

    Raises:
        ImportError: Modal SDK not installed
        Exception: Sandbox creation/connection failed
        FileNotFoundError: Setup script not found
        RuntimeError: Setup script failed
    """
    import modal

    from deepagents_cli.integrations.modal import ModalBackend

    console.print("[yellow]Starting Modal sandbox...[/yellow]")

    # Create ephemeral app (auto-cleans up on exit)
    app = modal.App("deepagents-sandbox")

    with app.run():
        if sandbox_id:
            sandbox = modal.Sandbox.from_id(sandbox_id=sandbox_id, app=app)
            should_cleanup = False
        else:
            sandbox = modal.Sandbox.create(app=app, workdir="/workspace")
            should_cleanup = True

            # Poll until running (Modal requires this)
            for _ in range(90):  # 180s timeout (90 * 2s)
                if sandbox.poll() is not None:  # Sandbox terminated unexpectedly
                    msg = "Modal sandbox terminated unexpectedly during startup"
                    raise RuntimeError(msg)
                # Check if sandbox is ready by attempting a simple command
                try:
                    process = sandbox.exec("echo", "ready", timeout=5)
                    process.wait()
                    if process.returncode == 0:
                        break
                except Exception:
                    pass
                time.sleep(2)
            else:
                # Timeout - cleanup and fail
                sandbox.terminate()
                msg = "Modal sandbox failed to start within 180 seconds"
                raise RuntimeError(msg)

        backend = ModalBackend(sandbox)
        console.print(f"[green]✓ Modal sandbox ready: {backend.id}[/green]")

        # Run setup script if provided
        if setup_script_path:
            _run_sandbox_setup(backend, setup_script_path)
        try:
            yield backend
        finally:
            if should_cleanup:
                try:
                    console.print(f"[dim]Terminating Modal sandbox {sandbox_id}...[/dim]")
                    sandbox.terminate()
                    console.print(f"[dim]✓ Modal sandbox {sandbox_id} terminated[/dim]")
                except Exception as e:
                    console.print(f"[yellow]⚠ Cleanup failed: {e}[/yellow]")


@contextmanager
def create_runloop_sandbox(
    *, sandbox_id: str | None = None, setup_script_path: str | None = None
) -> Generator[SandboxBackendProtocol, None, None]:
    """Create or connect to Runloop devbox.

    Args:
        sandbox_id: Optional existing devbox ID to reuse
        setup_script_path: Optional path to setup script to run after sandbox starts

    Yields:
        (RunloopBackend, devbox_id)

    Raises:
        ImportError: Runloop SDK not installed
        ValueError: RUNLOOP_API_KEY not set
        RuntimeError: Devbox failed to start within timeout
        FileNotFoundError: Setup script not found
        RuntimeError: Setup script failed
    """
    from runloop_api_client import Runloop

    from deepagents_cli.integrations.runloop import RunloopBackend

    bearer_token = os.environ.get("RUNLOOP_API_KEY")
    if not bearer_token:
        msg = "RUNLOOP_API_KEY environment variable not set"
        raise ValueError(msg)

    client = Runloop(bearer_token=bearer_token)

    console.print("[yellow]Starting Runloop devbox...[/yellow]")

    if sandbox_id:
        devbox = client.devboxes.retrieve(id=sandbox_id)
        should_cleanup = False
    else:
        devbox = client.devboxes.create()
        sandbox_id = devbox.id
        should_cleanup = True

        # Poll until running (Runloop requires this)
        for _ in range(90):  # 180s timeout (90 * 2s)
            status = client.devboxes.retrieve(id=devbox.id)
            if status.status == "running":
                break
            time.sleep(2)
        else:
            # Timeout - cleanup and fail
            client.devboxes.shutdown(id=devbox.id)
            msg = "Devbox failed to start within 180 seconds"
            raise RuntimeError(msg)

    console.print(f"[green]✓ Runloop devbox ready: {sandbox_id}[/green]")

    backend = RunloopBackend(devbox_id=devbox.id, client=client)

    # Run setup script if provided
    if setup_script_path:
        _run_sandbox_setup(backend, setup_script_path)
    try:
        yield backend
    finally:
        if should_cleanup:
            try:
                console.print(f"[dim]Shutting down Runloop devbox {sandbox_id}...[/dim]")
                client.devboxes.shutdown(id=devbox.id)
                console.print(f"[dim]✓ Runloop devbox {sandbox_id} terminated[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠ Cleanup failed: {e}[/yellow]")


@contextmanager
def create_daytona_sandbox(
    *, sandbox_id: str | None = None, setup_script_path: str | None = None
) -> Generator[SandboxBackendProtocol, None, None]:
    """Create Daytona sandbox.

    Args:
        sandbox_id: Optional existing sandbox ID to reuse
        setup_script_path: Optional path to setup script to run after sandbox starts

    Yields:
        (DaytonaBackend, sandbox_id)

    Note:
        Connecting to existing Daytona sandbox by ID may not be supported yet.
        If sandbox_id is provided, this will raise NotImplementedError.
    """
    from daytona import Daytona, DaytonaConfig

    from deepagents_cli.integrations.daytona import DaytonaBackend

    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        msg = "DAYTONA_API_KEY environment variable not set"
        raise ValueError(msg)

    if sandbox_id:
        msg = (
            "Connecting to existing Daytona sandbox by ID not yet supported. "
            "Create a new sandbox by omitting --sandbox-id."
        )
        raise NotImplementedError(msg)

    console.print("[yellow]Starting Daytona sandbox...[/yellow]")

    daytona = Daytona(DaytonaConfig(api_key=api_key))
    sandbox = daytona.create()
    sandbox_id = sandbox.id

    # Poll until running (Daytona requires this)
    for _ in range(90):  # 180s timeout (90 * 2s)
        # Check if sandbox is ready by attempting a simple command
        try:
            result = sandbox.process.exec("echo ready", timeout=5)
            if result.exit_code == 0:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        try:
            # Clean up if possible
            sandbox.delete()
        finally:
            msg = "Daytona sandbox failed to start within 180 seconds"
            raise RuntimeError(msg)

    backend = DaytonaBackend(sandbox)
    console.print(f"[green]✓ Daytona sandbox ready: {backend.id}[/green]")

    # Run setup script if provided
    if setup_script_path:
        _run_sandbox_setup(backend, setup_script_path)
    try:
        yield backend
    finally:
        console.print(f"[dim]Deleting Daytona sandbox {sandbox_id}...[/dim]")
        try:
            sandbox.delete()
            console.print(f"[dim]✓ Daytona sandbox {sandbox_id} terminated[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠ Cleanup failed: {e}[/yellow]")


@contextmanager
def create_agent_infra_sandbox(
    *, 
    sandbox_id: str | None = None, 
    setup_script_path: str | None = None,
    session_name: str = "default",
) -> Generator[SandboxBackendProtocol, None, None]:
    """Create or connect to Agent-Infra sandbox with a named session.

    This is the default sandbox provider for local development.
    No API keys required - just needs the Docker container running.
    
    Each session has its own isolated workspace at /home/gem/workspaces/{session_name}/

    Args:
        sandbox_id: Ignored (sandbox is always the same local instance)
        setup_script_path: Optional path to setup script to run after connection
        session_name: Name of the session/workspace to use (default: "default")

    Yields:
        AgentInfraBackend instance

    Raises:
        RuntimeError: If unable to connect to sandbox
    """
    import os
    from deepagents_cli.integrations.agent_infra import AgentInfraBackend

    base_url = os.environ.get("AGENT_INFRA_URL", "http://localhost:8090")
    timeout = float(os.environ.get("AGENT_INFRA_TIMEOUT", "60"))

    console.print("[yellow]Connecting to Agent-Infra sandbox...[/yellow]")

    backend = AgentInfraBackend(base_url=base_url, timeout=timeout)
    
    # Check if sandbox is running
    if not backend.health_check():
        msg = (
            f"Unable to connect to Agent-Infra sandbox at {base_url}. "
            "Make sure Docker container is running with: docker-compose up -d"
        )
        raise RuntimeError(msg)

    console.print(f"[green]✓ Agent-Infra sandbox ready: {backend.id}[/green]")
    console.print(f"[cyan]📁 Session: {session_name}[/cyan]")

    # Initialize workspace for this session
    # This creates the folder structure and agent.md file on first startup
    backend.initialize_workspace(session_name=session_name, agent_name="agent")

    # Run setup script if provided
    if setup_script_path:
        _run_sandbox_setup(backend, setup_script_path)

    try:
        yield backend
    finally:
        # No cleanup needed for local sandbox - it persists
        console.print("[dim]Agent-Infra sandbox session ended (sandbox continues running)[/dim]")


_PROVIDER_TO_WORKING_DIR = {
    "modal": "/workspace",
    "runloop": "/home/user",
    "daytona": "/home/daytona",
    "agent_infra": "/home/gem",
}


# Mapping of sandbox types to their context manager factories
_SANDBOX_PROVIDERS = {
    "modal": create_modal_sandbox,
    "runloop": create_runloop_sandbox,
    "daytona": create_daytona_sandbox,
    "agent_infra": create_agent_infra_sandbox,
}


@contextmanager
def create_sandbox(
    provider: str,
    *,
    sandbox_id: str | None = None,
    setup_script_path: str | None = None,
    session_name: str = "default",
) -> Generator[SandboxBackendProtocol, None, None]:
    """Create or connect to a sandbox of the specified provider.

    This is the unified interface for sandbox creation that delegates to
    the appropriate provider-specific context manager.

    Args:
        provider: Sandbox provider ("modal", "runloop", "daytona", "agent_infra")
        sandbox_id: Optional existing sandbox ID to reuse
        setup_script_path: Optional path to setup script to run after sandbox starts
        session_name: Session name for workspace isolation (agent_infra only)

    Yields:
        SandboxBackend instance
    """
    if provider not in _SANDBOX_PROVIDERS:
        msg = (
            f"Unknown sandbox provider: {provider}. "
            f"Available providers: {', '.join(get_available_sandbox_types())}"
        )
        raise ValueError(msg)

    sandbox_provider = _SANDBOX_PROVIDERS[provider]

    # Pass session_name only to agent_infra provider
    if provider == "agent_infra":
        with sandbox_provider(
            sandbox_id=sandbox_id, 
            setup_script_path=setup_script_path,
            session_name=session_name,
        ) as backend:
            yield backend
    else:
        with sandbox_provider(sandbox_id=sandbox_id, setup_script_path=setup_script_path) as backend:
            yield backend


def get_available_sandbox_types() -> list[str]:
    """Get list of available sandbox provider types.

    Returns:
        List of sandbox type names (e.g., ["modal", "runloop", "daytona"])
    """
    return list(_SANDBOX_PROVIDERS.keys())


def get_default_working_dir(provider: str) -> str:
    """Get the default working directory for a given sandbox provider.

    Args:
        provider: Sandbox provider name ("modal", "runloop", "daytona")

    Returns:
        Default working directory path as string

    Raises:
        ValueError: If provider is unknown
    """
    if provider in _PROVIDER_TO_WORKING_DIR:
        return _PROVIDER_TO_WORKING_DIR[provider]
    msg = f"Unknown sandbox provider: {provider}"
    raise ValueError(msg)


__all__ = [
    "create_sandbox",
    "get_available_sandbox_types",
    "get_default_working_dir",
]
