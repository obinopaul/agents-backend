import asyncio
import subprocess
import sys

from dataclasses import dataclass
from typing import Annotated, Literal

import anyio
import cappa
import granian

from cappa.output import error_format
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from sqlalchemy import text
from watchfiles import PythonFilter

from backend import __version__
from backend.common.enums import DataBaseType, PrimaryKeyType
from backend.common.exception.errors import BaseExceptionError
from backend.core.conf import settings
from backend.core.path_conf import BASE_PATH
from backend.database.db import async_db_session, create_tables, drop_tables
from backend.database.redis import redis_client
from backend.plugin.tools import get_plugin_sql, get_plugins
from backend.utils.console import console
from backend.utils.file_ops import install_git_plugin, install_zip_plugin, parse_sql_script
from backend.utils.import_parse import import_module_cached

output_help = '\nFor more information, try "[cyan]--help[/]"'


class CustomReloadFilter(PythonFilter):
    """Custom reload filter"""

    def __init__(self) -> None:
        super().__init__(extra_extensions=['.json', '.yaml', '.yml'])


async def init() -> None:
    panel_content = Text()
    panel_content.append('Database configuration', style='bold green')
    panel_content.append('\n\n  • Type: ')
    panel_content.append(f'{settings.DATABASE_TYPE}', style='yellow')
    panel_content.append('\n  • Database: ')
    panel_content.append(f'{settings.DATABASE_SCHEMA}', style='yellow')
    panel_content.append('\n  • Primary key mode: ')
    panel_content.append(
        f'{settings.DATABASE_PK_MODE}',
        style='yellow',
    )
    pk_details = panel_content.from_markup(
        '[link=https://fastapi-practices.github.io/fastapi_best_architecture_docs/backend/reference/pk.html]（了解详情）[/]'
    )
    panel_content.append(pk_details)
    panel_content.append('\n\nRedis configuration', style='bold green')
    panel_content.append('\n\n  • Database: ')
    panel_content.append(f'{settings.REDIS_DATABASE}', style='yellow')
    plugins = get_plugins()
    panel_content.append('\n\nInstalled plugins', style='bold green')
    panel_content.append('\n\n  • ')
    if plugins:
        panel_content.append(f'{", ".join(plugins)}', style='yellow')
    else:
        panel_content.append('None', style='dim')

    console.print(Panel(panel_content, title=f'agents-backend v{__version__} initialization', border_style='cyan', padding=(1, 2)))
    ok = Prompt.ask(
        'Are you sure to rebuild the database tables and execute all SQL scripts?', choices=['y', 'n'], default='n'
    )

    if ok.lower() == 'y':
        console.print('Initializing...', style='white')
        try:
            console.print('Dropping database tables', style='white')
            await drop_tables()
            console.print('Dropping Redis cache', style='white')
            await redis_client.delete_prefix(settings.JWT_USER_REDIS_PREFIX)
            await redis_client.delete_prefix(settings.TOKEN_EXTRA_INFO_REDIS_PREFIX)
            await redis_client.delete_prefix(settings.TOKEN_REDIS_PREFIX)
            await redis_client.delete_prefix(settings.TOKEN_REFRESH_REDIS_PREFIX)
            console.print('Creating database tables', style='white')
            await create_tables()
            console.print('Executing SQL scripts', style='white')
            sql_scripts = await get_sql_scripts()
            for sql_script in sql_scripts:
                console.print(f'Executing: {sql_script}', style='white')
                await execute_sql_scripts(sql_script, is_init=True)
            console.print('Initialization completed', style='green')
            console.print('\nTry [bold cyan]agents-backend run[/bold cyan] to start the service')
        except Exception as e:
            raise cappa.Exit(f'Initialization failed: {e}', code=1)
    else:
        console.print('Initialization cancelled', style='yellow')


def run(host: str, port: int, reload: bool, workers: int) -> None:  # noqa: FBT001
    url = f'http://{host}:{port}'
    docs_url = url + settings.FASTAPI_DOCS_URL
    redoc_url = url + settings.FASTAPI_REDOC_URL
    openapi_url = url + (settings.FASTAPI_OPENAPI_URL or '')

    panel_content = Text()
    panel_content.append('Python version:', style='bold cyan')
    panel_content.append(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}', style='white')

    panel_content.append('\nAPI request address: ', style='bold cyan')
    panel_content.append(f'{url}{settings.FASTAPI_API_V1_PATH}', style='blue')

    panel_content.append('\n\nEnvironment mode: ', style='bold green')
    env_style = 'yellow' if settings.ENVIRONMENT == 'dev' else 'green'
    panel_content.append(f'{settings.ENVIRONMENT.upper()}', style=env_style)

    plugins = get_plugins()
    panel_content.append('\nInstalled plugins: ', style='bold green')
    if plugins:
        panel_content.append(f'{", ".join(plugins)}', style='yellow')
    else:
        panel_content.append('None', style='white')

    if settings.ENVIRONMENT == 'dev':
        panel_content.append(f'\n\n📖 Swagger docs: {docs_url}', style='bold magenta')
        panel_content.append(f'\n📚 Redoc docs: {redoc_url}', style='bold magenta')
        panel_content.append(f'\n📡 OpenAPI JSON: {openapi_url}', style='bold magenta')

    panel_content.append('\n🌐 Architecture official docs: ', style='bold magenta')
    panel_content.append('https://fastapi-practices.github.io/fastapi_best_architecture_docs/')

    console.print(Panel(panel_content, title=f'agents-backend v{__version__}', border_style='purple', padding=(1, 2)))
    granian.Granian(
        target='backend.main:app',
        interface='asgi',
        address=host,
        port=port,
        reload=not reload,
        reload_filter=CustomReloadFilter,
        workers=workers,
    ).serve()


def run_celery_worker(log_level: Literal['info', 'debug']) -> None:
    try:
        subprocess.run(['celery', '-A', 'backend.app.task.celery', 'worker', '-l', f'{log_level}', '-P', 'gevent'])
    except KeyboardInterrupt:
        pass


def run_celery_beat(log_level: Literal['info', 'debug']) -> None:
    try:
        subprocess.run(['celery', '-A', 'backend.app.task.celery', 'beat', '-l', f'{log_level}'])
    except KeyboardInterrupt:
        pass


def run_celery_flower(port: int, basic_auth: str) -> None:
    try:
        subprocess.run([
            'celery',
            '-A',
            'backend.app.task.celery',
            'flower',
            f'--port={port}',
            f'--basic-auth={basic_auth}',
        ])
    except KeyboardInterrupt:
        pass


async def install_plugin(
    path: str,
    repo_url: str,
    no_sql: bool,  # noqa: FBT001
    db_type: DataBaseType,
    pk_type: PrimaryKeyType,
) -> None:
    if not path and not repo_url:
        raise cappa.Exit('path or repo_url must be specified', code=1)
    if path and repo_url:
        raise cappa.Exit('path and repo_url cannot be specified at the same time', code=1)

    plugin_name = None
    console.print('Installing plugin...', style='bold cyan')

    try:
        if path:
            plugin_name = await install_zip_plugin(file=path)
        if repo_url:
            plugin_name = await install_git_plugin(repo_url=repo_url)

        console.print(f'Plugin {plugin_name} installed successfully', style='bold green')

        sql_file = await get_plugin_sql(plugin_name, db_type, pk_type)
        if sql_file and not no_sql:
            console.print('Executing plugin SQL scripts...', style='bold cyan')
            await execute_sql_scripts(sql_file)

    except Exception as e:
        raise cappa.Exit(e.msg if isinstance(e, BaseExceptionError) else str(e), code=1)


async def get_sql_scripts() -> list[str]:
    sql_scripts = []
    db_dir = (
        BASE_PATH / 'sql' / 'mysql'
        if DataBaseType.mysql == settings.DATABASE_TYPE
        else BASE_PATH / 'sql' / 'postgresql'
    )
    main_sql_file = (
        db_dir / 'init_test_data.sql'
        if PrimaryKeyType.autoincrement == settings.DATABASE_PK_MODE
        else db_dir / 'init_snowflake_test_data.sql'
    )

    main_sql_path = anyio.Path(main_sql_file)
    if await main_sql_path.exists():
        sql_scripts.append(str(main_sql_file))

    plugins = get_plugins()
    for plugin in plugins:
        plugin_sql = await get_plugin_sql(plugin, settings.DATABASE_TYPE, settings.DATABASE_PK_MODE)
        if plugin_sql:
            sql_scripts.append(str(plugin_sql))

    return sql_scripts


async def execute_sql_scripts(sql_scripts: str, *, is_init: bool = False) -> None:
    async with async_db_session.begin() as db:
        try:
            stmts = await parse_sql_script(sql_scripts)
            for stmt in stmts:
                await db.execute(text(stmt))
        except Exception as e:
            raise cappa.Exit(f'SQL script execution failed: {e}', code=1)

    if not is_init:
        console.print('SQL script execution completed', style='bold green')


async def import_table(
    app: str,
    table_schema: str,
    table_name: str,
) -> None:
    from backend.plugin.code_generator.schema.code import ImportParam
    from backend.plugin.code_generator.service.code_service import gen_service

    try:
        obj = ImportParam(app=app, table_schema=table_schema, table_name=table_name)
        async with async_db_session.begin() as db:
            await gen_service.import_business_and_model(db=db, obj=obj)
        console.log('Import completed', style='bold green')
        console.log('\nTry [bold cyan]agents-backend codegen[/bold cyan] to generate code')
    except Exception as e:
        raise cappa.Exit(e.msg if isinstance(e, BaseExceptionError) else str(e), code=1)


async def generate() -> None:
    from backend.plugin.code_generator.service.business_service import gen_business_service
    from backend.plugin.code_generator.service.code_service import gen_service

    try:
        ids = []
        async with async_db_session() as db:
            results = await gen_business_service.get_all(db=db)

        if not results:
            raise cappa.Exit('[red]No available code generation business! Please import first![/]')

        table = Table(show_header=True, header_style='bold magenta')
        table.add_column('Business_ID', style='cyan', no_wrap=True, justify='center')
        table.add_column('Application Name', style='green', no_wrap=True)
        table.add_column('Generation Path', style='yellow')
        table.add_column('Remark', style='blue')

        for result in results:
            ids.append(result.id)
            table.add_row(
                str(result.id),
                result.app_name,
                result.gen_path or f'Application {result.app_name} root path',
                result.remark or '',
            )

        console.print(table)
        business = IntPrompt.ask('Please select a business ID', choices=[str(_id) for _id in ids])

        async with async_db_session.begin() as db:
            gen_path = await gen_service.generate(db=db, pk=business)
    except Exception as e:
        raise cappa.Exit(e.msg if isinstance(e, BaseExceptionError) else str(e), code=1)

    console.print('\nCode generation completed', style='bold green')
    console.print(Text('\nDetails please view:'), Text(str(gen_path), style='bold magenta'))


@cappa.command(help='Initialize agents-backend project', default_long=True)
@dataclass
class Init:
    async def __call__(self) -> None:
        await init()


@cappa.command(help='Run API service', default_long=True)
@dataclass
class Run:
    host: Annotated[
        str,
        cappa.Arg(
            default='127.0.0.1',
            help='提供服务的主机 IP 地址，对于本地开发，请使用 `127.0.0.1`。'
            '要启用公共访问，例如在局域网中，请使用 `0.0.0.0`',
        ),
    ]
    port: Annotated[
        int,
        cappa.Arg(default=8000, help='提供服务的主机端口号'),
    ]
    no_reload: Annotated[
        bool,
        cappa.Arg(default=False, help='禁用在（代码）文件更改时自动重新加载服务器'),
    ]
    workers: Annotated[
        int,
        cappa.Arg(default=1, help='使用多个工作进程，必须与 `--no-reload` 同时使用'),
    ]

    def __call__(self) -> None:
        run(host=self.host, port=self.port, reload=self.no_reload, workers=self.workers)


@cappa.command(help='Run Celery worker service', default_long=True)
@dataclass
class Worker:
    log_level: Annotated[
        Literal['info', 'debug'],
        cappa.Arg(short='-l', default='info', help='Log level'),
    ]

    def __call__(self) -> None:
        run_celery_worker(log_level=self.log_level)


@cappa.command(help='Run Celery beat service', default_long=True)
@dataclass
class Beat:
    log_level: Annotated[
        Literal['info', 'debug'],
        cappa.Arg(short='-l', default='info', help='Log level'),
    ]

    def __call__(self) -> None:
        run_celery_beat(log_level=self.log_level)


@cappa.command(help='Run Celery flower service', default_long=True)
@dataclass
class Flower:
    port: Annotated[
        int,
        cappa.Arg(default=8555, help='Provide service host port'),
    ]
    basic_auth: Annotated[
        str,
        cappa.Arg(default='admin:123456', help='Page login username and password'),
    ]

    def __call__(self) -> None:
        run_celery_flower(port=self.port, basic_auth=self.basic_auth)


@cappa.command(help='Run Celery services')
@dataclass
class Celery:
    subcmd: cappa.Subcommands[Worker | Beat | Flower]


@cappa.command(help='Add plugin', default_long=True)
@dataclass
class Add:
    path: Annotated[
        str | None,
        cappa.Arg(help='ZIP plugin local full path'),
    ]
    repo_url: Annotated[
        str | None,
        cappa.Arg(help='Git plugin repository address'),
    ]
    no_sql: Annotated[
        bool,
        cappa.Arg(default=False, help='Disable plugin SQL script automatic execution'),
    ]
    db_type: Annotated[
        DataBaseType,
        cappa.Arg(default='postgresql', help='Database type for executing plugin SQL scripts'),
    ]
    pk_type: Annotated[
        PrimaryKeyType,
        cappa.Arg(default='autoincrement', help='Primary key type for executing plugin SQL scripts'),
    ]

    async def __call__(self) -> None:
        await install_plugin(self.path, self.repo_url, self.no_sql, self.db_type, self.pk_type)


@cappa.command(help='Import code generation business and model columns', default_long=True)
@dataclass
class Import:
    app: Annotated[
        str,
        cappa.Arg(help='Application name, used for code generation to specified app'),
    ]
    table_schema: Annotated[
        str,
        cappa.Arg(short='tc', default='fba', help='数据库名'),
    ]
    table_name: Annotated[
        str,
        cappa.Arg(short='tn', help='数据库表名'),
    ]

    def __post_init__(self) -> None:
        try:
            import_module_cached('backend.plugin.code_generator')
        except ImportError:
            raise cappa.Exit('Code generation plugin does not exist, please install this plugin first')

    async def __call__(self) -> None:
        await import_table(self.app, self.table_schema, self.table_name)


@cappa.command(name='codegen', help='Code generation (Experience complete function, please deploy agents-backend vben frontend project by yourself)', default_long=True)
@dataclass
class CodeGenerator:
    subcmd: cappa.Subcommands[Import | None] = None

    def __post_init__(self) -> None:
        try:
            import_module_cached('backend.plugin.code_generator')
        except ImportError:
            raise cappa.Exit('Code generation plugin does not exist, please install this plugin first')

    async def __call__(self) -> None:
        await generate()


@cappa.command(help='Run the AI Agent interactive chat', default_long=True)
@dataclass
class Agent:
    debug: Annotated[bool, cappa.Arg(default=False, help='Enable debug logging')] = False
    enable_background_investigation: Annotated[bool, cappa.Arg(default=True, help='Enable background web search')] = True

    def __call__(self) -> None:
        # Import strictly inside command to avoid circular imports or heavy startup
        from InquirerPy import inquirer
        from backend.src.config.questions import BUILT_IN_QUESTIONS, BUILT_IN_QUESTIONS_ZH_CN
        from backend.src.workflow import run_agent_workflow_async
        
        # Interactive Mode Logic (Ported from main_2.py)
        language = inquirer.select(
            message="Select language / 选择语言:",
            choices=["English", "中文"],
        ).execute()

        questions = BUILT_IN_QUESTIONS if language == "English" else BUILT_IN_QUESTIONS_ZH_CN
        ask_own_option = "[Ask my own question]" if language == "English" else "[自定义问题]"

        initial_question = inquirer.select(
            message=("What do you want to know?" if language == "English" else "您想了解什么?"),
            choices=[ask_own_option] + questions,
        ).execute()

        if initial_question == ask_own_option:
            initial_question = inquirer.text(
                message=("What do you want to know?" if language == "English" else "您想了解什么?"),
            ).execute()

        asyncio.run(
            run_agent_workflow_async(
                user_input=initial_question,
                debug=self.debug,
                enable_background_investigation=self.enable_background_investigation,
            )
        )


@cappa.command(help='An efficient agents-backend command line interface', default_long=True)
@dataclass
class FbaCli:
    sql: Annotated[
        str,
        cappa.Arg(value_name='PATH', default='', show_default=False, help='Execute SQL scripts in a transaction'),
    ]
    subcmd: cappa.Subcommands[Init | Run | Celery | Add | CodeGenerator | Agent | None] = None

    async def __call__(self) -> None:
        if self.sql:
            await execute_sql_scripts(self.sql)


def main() -> None:
    output = cappa.Output(error_format=f'{error_format}\n{output_help}')
    asyncio.run(cappa.invoke_async(FbaCli, version=__version__, output=output))
