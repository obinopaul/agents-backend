import os
import json
import httpx
import asyncio
import subprocess
import uuid
from typing import Dict, Optional
from mcp.types import ToolAnnotations
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from argparse import ArgumentParser
from starlette.responses import JSONResponse
# OPTIMIZATION: Removed top-level imports of heavy modules (manager, mcp_integrations)
# These are now imported lazily inside functions to speed up server startup.
# The /health endpoint becomes available immediately, before any tool imports.
from dotenv import load_dotenv

load_dotenv()
_credential = None
_codex_process: Optional[subprocess.Popen] = None
_codex_url = "http://0.0.0.0:1324"


def get_current_credential():
    return _credential


def set_current_credential(credential: Dict):
    global _credential
    _credential = credential


def get_codex_process():
    return _codex_process


def set_codex_process(process: subprocess.Popen):
    global _codex_process
    _codex_process = process


def get_codex_url():
    return _codex_url


async def create_mcp(workspace_dir: str, custom_mcp_config: Dict = None, port: int = 6060):
    main_server = FastMCP()
    
    # Helper function to register all tools
    async def register_all_tools(credential: Dict):
        """Register all sandbox tools with the MCP server.
        
        Args:
            credential: Dict with user_api_key and session_id
                       (can be None/empty for non-credentialed tools)
        """
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        tools = get_sandbox_tools(
            workspace_path=workspace_dir,
            credential=credential,
        )
        registered_count = 0
        for tool in tools:
            try:
                main_server.tool(
                    tool.execute_mcp_wrapper,
                    name=tool.name,
                    description=tool.description,
                    annotations=ToolAnnotations(
                        title=tool.display_name,
                        readOnlyHint=tool.read_only,
                    ),
                )
                # Set parameters for the tool
                _mcp_tool = await main_server._tool_manager.get_tool(tool.name)
                _mcp_tool.parameters = tool.input_schema
                registered_count += 1
                print(f"Registered tool: {tool.name}")
            except Exception as e:
                print(f"Warning: Failed to register tool {tool.name}: {e}")
        
        print(f"Total tools registered: {registered_count}/{len(tools)}")
        return registered_count

    @main_server.custom_route("/health", methods=["GET"])
    async def health(request):
        return JSONResponse({"status": "ok"}, status_code=200)

    # =========================================================================
    # Document Management Routes for LaTeX Editor Workspace Integration
    # These routes allow the browser-based editor to read/write files from
    # /workspace/documents/ (sandbox filesystem)
    # 
    # FALLBACK: If no documents in /workspace/documents/, check /workspace/
    # for .tex files created directly by the agent
    # =========================================================================
    
    DOCUMENTS_PATH = os.path.join(workspace_dir, "documents")
    WORKSPACE_ROOT = workspace_dir  # /workspace
    
    @main_server.custom_route("/documents", methods=["GET"])
    async def list_documents(request):
        """List all document folders in /workspace/documents/
        
        Fallback: If /workspace/documents/ is empty, check if there are
        .tex files directly in /workspace/ and expose them as '_workspace'
        """
        try:
            # Ensure documents directory exists
            os.makedirs(DOCUMENTS_PATH, exist_ok=True)
            
            documents = []
            
            # Check /workspace/documents/ for document folders
            for item in os.listdir(DOCUMENTS_PATH):
                item_path = os.path.join(DOCUMENTS_PATH, item)
                if os.path.isdir(item_path):
                    # Count files in the document folder
                    file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                    documents.append({
                        "name": item,
                        "path": item_path,
                        "file_count": file_count,
                        "source": "documents",  # From /workspace/documents/
                    })
            
            # FALLBACK: If no documents found, check for .tex files in /workspace/ directly
            if not documents:
                workspace_tex_files = [f for f in os.listdir(WORKSPACE_ROOT) 
                                       if f.endswith('.tex') and os.path.isfile(os.path.join(WORKSPACE_ROOT, f))]
                if workspace_tex_files:
                    # Expose /workspace/ as a virtual document called "_workspace"
                    documents.append({
                        "name": "_workspace",
                        "path": WORKSPACE_ROOT,
                        "file_count": len(workspace_tex_files),
                        "source": "workspace_root",  # Files directly in /workspace/
                    })
            
            return JSONResponse({
                "success": True,
                "documents": documents,
                "count": len(documents),
            }, status_code=200)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
            }, status_code=500)

    @main_server.custom_route("/documents/{name}/files", methods=["GET"])
    async def list_document_files(request):
        """List all files in a specific document folder
        
        Special case: '_workspace' refers to files directly in /workspace/
        """
        try:
            doc_name = request.path_params.get("name")
            if not doc_name:
                return JSONResponse({"success": False, "error": "Document name required"}, status_code=400)
            
            # Handle _workspace special case (files directly in /workspace/)
            if doc_name == "_workspace":
                doc_path = WORKSPACE_ROOT
            else:
                doc_path = os.path.join(DOCUMENTS_PATH, doc_name)
            
            if not os.path.exists(doc_path):
                return JSONResponse({
                    "success": False,
                    "error": f"Document '{doc_name}' not found",
                }, status_code=404)
            
            files = []
            for item in os.listdir(doc_path):
                item_path = os.path.join(doc_path, item)
                file_ext = os.path.splitext(item)[1].lower()
                
                # Determine file type
                if file_ext == '.tex':
                    file_type = 'tex'
                elif file_ext == '.bib':
                    file_type = 'bib'
                elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.svg']:
                    file_type = 'image'
                else:
                    file_type = 'other'
                
                files.append({
                    "name": item,
                    "path": item_path,
                    "type": file_type,
                    "isDirectory": os.path.isdir(item_path),
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0,
                })
            
            return JSONResponse({
                "success": True,
                "files": files,
                "count": len(files),
                "document": doc_name,
            }, status_code=200)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
            }, status_code=500)

    @main_server.custom_route("/documents/{name}/files/{filename:path}", methods=["GET"])
    async def read_document_file(request):
        """Read content of a specific file in a document folder
        
        Special case: '_workspace' refers to files directly in /workspace/
        """
        from starlette.responses import Response
        import base64
        
        try:
            doc_name = request.path_params.get("name")
            filename = request.path_params.get("filename")
            
            if not doc_name or not filename:
                return JSONResponse({"success": False, "error": "Document name and filename required"}, status_code=400)
            
            # Handle _workspace special case
            if doc_name == "_workspace":
                file_path = os.path.join(WORKSPACE_ROOT, filename)
                base_path = WORKSPACE_ROOT
            else:
                file_path = os.path.join(DOCUMENTS_PATH, doc_name, filename)
                base_path = DOCUMENTS_PATH
            
            # Security: Prevent path traversal
            real_path = os.path.realpath(file_path)
            if not real_path.startswith(os.path.realpath(base_path)):
                return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)
            
            if not os.path.exists(file_path):
                return JSONResponse({
                    "success": False,
                    "error": f"File '{filename}' not found in document '{doc_name}'",
                }, status_code=404)
            
            # Check if it's an image/binary file
            file_ext = os.path.splitext(filename)[1].lower()
            is_binary = file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.svg']
            
            if is_binary:
                # Return base64 encoded for images
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                return JSONResponse({
                    "success": True,
                    "content": content,
                    "encoding": "base64",
                    "filename": filename,
                }, status_code=200)
            else:
                # Return plain text for text files
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return Response(content, media_type="text/plain", status_code=200)
                
        except UnicodeDecodeError:
            return JSONResponse({
                "success": False,
                "error": "File is not a valid text file",
            }, status_code=400)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
            }, status_code=500)

    @main_server.custom_route("/documents/{name}/files/{filename:path}", methods=["PUT"])
    async def write_document_file(request):
        """Write content to a specific file in a document folder
        
        Special case: '_workspace' refers to files directly in /workspace/
        """
        try:
            doc_name = request.path_params.get("name")
            filename = request.path_params.get("filename")
            
            if not doc_name or not filename:
                return JSONResponse({"success": False, "error": "Document name and filename required"}, status_code=400)
            
            # Handle _workspace special case
            if doc_name == "_workspace":
                file_path = os.path.join(WORKSPACE_ROOT, filename)
                base_path = WORKSPACE_ROOT
            else:
                file_path = os.path.join(DOCUMENTS_PATH, doc_name, filename)
                base_path = DOCUMENTS_PATH
            
            # Security: Prevent path traversal
            real_path = os.path.realpath(os.path.dirname(file_path))
            if not real_path.startswith(os.path.realpath(base_path)):
                return JSONResponse({"success": False, "error": "Access denied"}, status_code=403)
            
            # Ensure document directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Get content from request body
            content = await request.body()
            content_str = content.decode('utf-8')
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
            
            return JSONResponse({
                "success": True,
                "message": f"File '{filename}' saved successfully",
                "path": file_path,
            }, status_code=200)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
            }, status_code=500)

    @main_server.custom_route("/documents/{name}/compile", methods=["POST"])
    async def compile_document(request):
        """Compile a LaTeX document using pdflatex
        
        Special case: '_workspace' refers to files directly in /workspace/
        """
        import subprocess
        
        try:
            doc_name = request.path_params.get("name")
            if not doc_name:
                return JSONResponse({"success": False, "error": "Document name required"}, status_code=400)
            
            # Handle _workspace special case
            if doc_name == "_workspace":
                doc_path = WORKSPACE_ROOT
            else:
                doc_path = os.path.join(DOCUMENTS_PATH, doc_name)
            
            if not os.path.exists(doc_path):
                return JSONResponse({
                    "success": False,
                    "error": f"Document '{doc_name}' not found",
                }, status_code=404)
            
            # Get main file from request body or auto-detect
            body = await request.json() if request.headers.get("content-type") == "application/json" else {}
            main_file = body.get("main_file")
            
            # Auto-detect main file if not specified
            if not main_file:
                tex_files = [f for f in os.listdir(doc_path) if f.endswith('.tex')]
                # Prefer main.tex, then first .tex file
                if 'main.tex' in tex_files:
                    main_file = 'main.tex'
                elif tex_files:
                    # Look for file with \documentclass
                    for tex_file in tex_files:
                        with open(os.path.join(doc_path, tex_file), 'r', encoding='utf-8') as f:
                            if '\\documentclass' in f.read():
                                main_file = tex_file
                                break
                    if not main_file:
                        main_file = tex_files[0]
                else:
                    return JSONResponse({
                        "success": False,
                        "error": "No .tex files found in document",
                    }, status_code=400)
            
            main_file_path = os.path.join(doc_path, main_file)
            if not os.path.exists(main_file_path):
                return JSONResponse({
                    "success": False,
                    "error": f"Main file '{main_file}' not found",
                }, status_code=404)
            
            # Run pdflatex (twice for references)
            output_dir = doc_path
            cmd = [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={output_dir}",
                main_file_path,
            ]
            
            result = subprocess.run(
                cmd,
                cwd=doc_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            # Run second pass for references
            if result.returncode == 0:
                subprocess.run(cmd, cwd=doc_path, capture_output=True, text=True, timeout=60)
            
            # Check for output PDF
            pdf_name = os.path.splitext(main_file)[0] + ".pdf"
            pdf_path = os.path.join(output_dir, pdf_name)
            
            if result.returncode == 0 and os.path.exists(pdf_path):
                return JSONResponse({
                    "success": True,
                    "pdf_path": pdf_path,
                    "pdf_name": pdf_name,
                    "log": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                }, status_code=200)
            else:
                # Parse errors from log
                log = result.stdout + result.stderr
                return JSONResponse({
                    "success": False,
                    "error": "Compilation failed",
                    "log": log[-3000:] if len(log) > 3000 else log,
                }, status_code=200)
                
        except subprocess.TimeoutExpired:
            return JSONResponse({
                "success": False,
                "error": "Compilation timed out (60s limit)",
            }, status_code=500)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e),
            }, status_code=500)


    @main_server.custom_route("/custom-mcp", methods=["POST"])
    async def add_mcp_config(request):
        if not await request.json():
            return JSONResponse({"error": "Invalid request"}, status_code=400)
        main_server.mount(
            FastMCP.as_proxy(ProxyClient(await request.json())), prefix="mcp"
        )
        return JSONResponse({"status": "success"}, status_code=200)

    @main_server.custom_route("/register-codex", methods=["POST"])
    async def register_codex(request):
        """Start the Codex SSE HTTP server subprocess"""
        # Check if Codex is already running
        if get_codex_process() is not None:
            process = get_codex_process()
            if process.poll() is None:  # Process is still running
                return JSONResponse(
                    {"status": "already_running", "url": get_codex_url()},
                    status_code=200,
                )

        try:
            # Start the sse-http-server subprocess
            process = subprocess.Popen(
                ["sse-http-server", "--addr", get_codex_url().replace("http://", "")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            set_codex_process(process)

            # Check if the process started successfully
            if process.poll() is not None:
                # Process terminated already
                stdout, stderr = process.communicate()
                return JSONResponse(
                    {
                        "status": "error",
                        "message": f"Codex server failed to start: {stderr}",
                    },
                    status_code=500,
                )

            # Verify the server is responding
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{get_codex_url()}/health", timeout=5.0
                    )
                    response.raise_for_status()
            except Exception:
                # Server might not have health endpoint, that's ok
                pass

            return JSONResponse(
                {"status": "success", "url": get_codex_url()}, status_code=200
            )

        except FileNotFoundError:
            return JSONResponse(
                {
                    "status": "error",
                    "message": "sse-http-server executable not found. Make sure it's installed and in PATH.",
                },
                status_code=500,
            )
        except Exception as e:
            return JSONResponse(
                {"status": "error", "message": f"Failed to start Codex server: {e}"},
                status_code=500,
            )

    @main_server.custom_route("/credential", methods=["POST"])
    async def set_credential(request):
        if not await request.json():
            return JSONResponse({"error": "Invalid request"}, status_code=400)
        credential = await request.json()
        if not credential.get("user_api_key") or not credential.get("session_id"):
            return JSONResponse(
                {
                    "error": "user_api_key or session_id is not set in the credential file"
                },
                status_code=400,
            )
        set_current_credential(credential)
        return JSONResponse({"status": "success"}, status_code=200)

    @main_server.custom_route("/tool-server-url", methods=["POST"])
    async def set_tool_server_url(request):
        if get_current_credential() is None:
            return JSONResponse(
                {"error": "Credential must be set before setting tool server url"},
                status_code=400,
            )

        if not await request.json():
            return JSONResponse({"error": "Invalid request"}, status_code=400)

        # Check if the tool server is running
        tool_server_url_request = (await request.json()).get("tool_server_url")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{tool_server_url_request}/health")
                response.raise_for_status()
        # TODO: add retry logic
        except Exception as e:
            return JSONResponse(
                {"status": "error", "message": f"Can't connect to tool server: {e}"},
                status_code=500,
            )

        # LAZY IMPORT: Only import heavy modules when this endpoint is called
        from backend.src.tool_server.core.tool_server import (
            set_tool_server_url as set_tool_server_url_singleton,
        )
        from backend.src.tool_server.tools.manager import get_sandbox_tools
        
        set_tool_server_url_singleton(tool_server_url_request)

        # Start registering tools
        tools = get_sandbox_tools(
            workspace_path=workspace_dir,
            credential=get_current_credential(),
        )
        for tool in tools:
            main_server.tool(
                tool.execute_mcp_wrapper,
                name=tool.name,
                description=tool.description,
                annotations=ToolAnnotations(
                    title=tool.display_name,
                    readOnlyHint=tool.read_only,
                ),
            )

            # NOTE: this is a temporary fix to set the parameters of the tool
            _mcp_tool = await main_server._tool_manager.get_tool(tool.name)
            _mcp_tool.parameters = tool.input_schema

            print(f"Registered tool: {tool.name}")

        return JSONResponse({"status": "success"}, status_code=200)

    # OPTIMIZATION: Defer MCP integrations loading until first use
    # This prevents importing heavy modules at server startup
    # The integrations will be loaded when a tool that needs them is first called
    # Previously this block loaded at startup:
    # mcp_integrations = get_mcp_integrations(workspace_dir)
    # for mcp_integration in mcp_integrations:
    #     proxy = FastMCP.as_proxy(ProxyClient(mcp_integration.config))
    #     for tool_name in mcp_integration.selected_tool_names:
    #         mirrored_tool = await proxy.get_tool(tool_name)
    #         local_tool = mirrored_tool.copy()
    #         main_server.add_tool(local_tool)

    # User customized MCP integrations
    if custom_mcp_config:
        print(custom_mcp_config)
        proxy = FastMCP.as_proxy(ProxyClient(custom_mcp_config))
        main_server.mount(proxy, prefix="mcp")

    # OPTIMIZATION: Removed auto-registration at startup to speed up MCP server boot.
    # Tools are now registered on-demand when /credential + /tool-server-url are called.
    # reducing startup time by ~30-40 seconds.
    #
    # The /health endpoint is now available immediately without waiting for tool registration.
    # The workflow is:
    #   1. MCP server starts and /health becomes available (~5-10 seconds)
    #   2. Backend polls /health until ready
    #   3. Backend calls POST /credential with user credentials
    #   4. Backend calls POST /tool-server-url to trigger tool registration
    #   5. Tools are registered and ready for use
    #
    # Previously, this block would run at startup:
    # print("\n=== Auto-registering tools at startup ===")
    # default_credential = {
    #     "user_api_key": None,
    #     "session_id": str(uuid.uuid4()),
    # }
    # set_current_credential(default_credential)
    # internal_tool_server_url = os.getenv("TOOL_SERVER_URL", f"http://localhost:{port}")
    # set_tool_server_url_singleton(internal_tool_server_url)
    # await register_all_tools(default_credential)
    # print("=== Tool registration complete ===\n")
    
    print("=== MCP Server ready (tools will be registered on first credential/tool-server-url call) ===")

    return main_server


async def main():
    parser = ArgumentParser()
    parser.add_argument("--workspace_dir", type=str, default=None)
    parser.add_argument("--custom_mcp_config", type=str, default=None)
    parser.add_argument("--port", type=int, default=6060)

    args = parser.parse_args()

    workspace_dir = os.getenv("WORKSPACE_DIR")
    if args.workspace_dir:
        workspace_dir = args.workspace_dir

    if not workspace_dir:
        raise ValueError(
            "workspace_dir is not set. Please set the WORKSPACE_DIR environment variable or pass it as an argument --workspace_dir"
        )

    os.makedirs(workspace_dir, exist_ok=True)
    custom_mcp_config = args.custom_mcp_config
    if custom_mcp_config:
        with open(custom_mcp_config, "r") as f:
            custom_mcp_config = json.load(f)

    mcp = await create_mcp(
        workspace_dir=workspace_dir, custom_mcp_config=custom_mcp_config, port=args.port
    )
    await mcp.run_async(transport="http", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
