from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

from backend.core.registrar import register_app
from backend.plugin.tools import get_plugins, install_requirements
from backend.utils.console import console
from backend.utils.timezone import timezone
import os
import asyncio
import logging

# To ensure compatibility with Windows event loop issues when using Uvicorn and Asyncio Checkpointer,
# This is necessary because some libraries expect a selector-based event loop.
if os.name == "nt":
    logging.getLogger(__name__).info("Setting Windows event loop policy for asyncio")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_log_prefix = f'{timezone.to_str(timezone.now(), "%Y-%m-%d %H:%M:%S.%M0")} | {"INFO": <8} | - | '
console.print(Text(f'{_log_prefix}Checking plugin dependencies...', style='bold cyan'))

_plugins = get_plugins()

with Progress(
    SpinnerColumn(finished_text=f'[bold green]{_log_prefix}Plugin dependencies checked[/]'),
    TextColumn('{task.description}'),
    TextColumn('{task.completed}/{task.total}', style='bold green'),
    TimeElapsedColumn(),
    console=console,
) as progress:
    task = progress.add_task('Installing plugin dependencies...', total=len(_plugins))
    for plugin in _plugins:
        progress.update(task, description=f'[bold magenta]Installing plugin {plugin} dependencies...[/]')
        install_requirements(plugin)
        progress.advance(task)
    progress.update(task, description='[bold green]-[/]')

console.print(Text(f'{_log_prefix}Starting service...', style='bold magenta'))

app = register_app()
