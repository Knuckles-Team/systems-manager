#!/usr/bin/python
import sys

# coding: utf-8
import os
import argparse
import logging
import uvicorn
import httpx
from contextlib import asynccontextmanager
from typing import Optional, Any
import json

# Add parent directory to path to allow running as script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic_ai import Agent, ModelSettings
from pydantic_ai.mcp import load_mcp_servers, MCPServerStreamableHTTP, MCPServerSSE
from pydantic_ai_skills import SkillsToolset
from fasta2a import Skill
from systems_manager.utils import (
    get_mcp_config_path,
    get_skills_path,
    to_boolean,
    to_integer,
    to_float,
    to_list,
    to_dict,
    load_skills_from_directory,
    create_model,
    prune_large_messages,
)

from fastapi import FastAPI, Request
from starlette.responses import Response, StreamingResponse
from pydantic import ValidationError
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.ag_ui import AGUIAdapter

__version__ = "1.2.10"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logging.getLogger("pydantic_ai").setLevel(logging.INFO)
logging.getLogger("fastmcp").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = to_integer(os.getenv("PORT", "9000"))
DEFAULT_DEBUG = to_boolean(os.getenv("DEBUG", "False"))
DEFAULT_PROVIDER = os.getenv("PROVIDER", "openai")
DEFAULT_MODEL_ID = os.getenv("MODEL_ID", "qwen/qwen3-coder-next")
DEFAULT_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://host.docker.internal:1234/v1")
DEFAULT_LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
DEFAULT_MCP_URL = os.getenv("MCP_URL", None)
DEFAULT_MCP_CONFIG = os.getenv("MCP_CONFIG", get_mcp_config_path())
DEFAULT_SKILLS_DIRECTORY = os.getenv("SKILLS_DIRECTORY", get_skills_path())
DEFAULT_ENABLE_WEB_UI = to_boolean(os.getenv("ENABLE_WEB_UI", "False"))
DEFAULT_SSL_VERIFY = to_boolean(os.getenv("SSL_VERIFY", "True"))

DEFAULT_MAX_TOKENS = to_integer(os.getenv("MAX_TOKENS", "16384"))
DEFAULT_TEMPERATURE = to_float(os.getenv("TEMPERATURE", "0.7"))
DEFAULT_TOP_P = to_float(os.getenv("TOP_P", "1.0"))
DEFAULT_TIMEOUT = to_float(os.getenv("TIMEOUT", "32400.0"))
DEFAULT_TOOL_TIMEOUT = to_float(os.getenv("TOOL_TIMEOUT", "32400.0"))
DEFAULT_PARALLEL_TOOL_CALLS = to_boolean(os.getenv("PARALLEL_TOOL_CALLS", "True"))
DEFAULT_SEED = to_integer(os.getenv("SEED", None))
DEFAULT_PRESENCE_PENALTY = to_float(os.getenv("PRESENCE_PENALTY", "0.0"))
DEFAULT_FREQUENCY_PENALTY = to_float(os.getenv("FREQUENCY_PENALTY", "0.0"))
DEFAULT_LOGIT_BIAS = to_dict(os.getenv("LOGIT_BIAS", None))
DEFAULT_STOP_SEQUENCES = to_list(os.getenv("STOP_SEQUENCES", None))
DEFAULT_EXTRA_HEADERS = to_dict(os.getenv("EXTRA_HEADERS", None))
DEFAULT_EXTRA_BODY = to_dict(os.getenv("EXTRA_BODY", None))


AGENT_NAME = "Systems Manager Agent"
AGENT_DESCRIPTION = "A specialist agent for managing system configurations, installations, and maintenance."

# =============================================================================
# Agent Prompts
# =============================================================================

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Systems Manager Supervisor Agent.\n"
    "Your role is to orchestrate a team of specialized agents to manage system configurations, installations, and maintenance.\n"
    "You have access to the following specialists:\n"
    "1.  **System Specialist**: General system updates, health checks, uptime, and hardware stats.\n"
    "2.  **Filesystem Specialist**: File and directory management (list, search, grep, create, delete).\n"
    "3.  **Shell Specialist**: Shell profile management and alias creation.\n"
    "4.  **Python Specialist**: Python environment management (uv, venvs, packages).\n"
    "5.  **Node Specialist**: Node.js environment management (nvm, node versions).\n"
    "6.  **Service Specialist**: System service management (start, stop, enable, disable).\n"
    "7.  **Process Specialist**: Process management (list, kill, details).\n"
    "8.  **Network Specialist**: Network diagnostics (interfaces, ports, ping, DNS).\n"
    "9.  **Disk Specialist**: Disk usage and partition information.\n"
    "10. **User Specialist**: User and group management.\n"
    "11. **Log Specialist**: System and file log viewing.\n"
    "12. **Cron Specialist**: Scheduled task management.\n"
    "13. **Firewall Specialist**: Firewall rule management.\n"
    "14. **SSH Specialist**: SSH key management.\n\n"
    "**Routing Guidelines:**\n"
    "- Delegates tasks to the appropriate specialist based on the user's request.\n"
    "- For complex requests involving multiple domains (e.g., 'install node, create a project dir, and add an alias'), break them down and call respective agents in sequence or parallel as appropriate.\n"
    "- Always report the final outcome to the user.\n"
)

SYSTEM_PROMPT = (
    "You are the System Specialist.\n"
    "Responsibilities: System updates, health checks, stats, uptime, and package info.\n"
    "Tools: update, clean, optimize, get_os_statistics, get_hardware_statistics, etc."
)

FILESYSTEM_PROMPT = (
    "You are the Filesystem Specialist.\n"
    "Responsibilities: Manage files and directories.\n"
    "Tools: list_files, search_files, grep_files, manage_file."
)

SHELL_PROMPT = (
    "You are the Shell Specialist.\n"
    "Responsibilities: Manage shell profiles and aliases.\n"
    "Tools: add_shell_alias."
)

PYTHON_PROMPT = (
    "You are the Python Specialist.\n"
    "Responsibilities: Manage Python environments and packages using uv.\n"
    "Tools: install_uv, create_python_venv, install_python_package_uv."
)

NODE_PROMPT = (
    "You are the Node.js Specialist.\n"
    "Responsibilities: Manage Node.js versions and nvm.\n"
    "Tools: install_nvm, install_node, use_node."
)

SERVICE_PROMPT = (
    "You are the Service Specialist.\n"
    "Responsibilities: Manage system services (systemd/Windows services).\n"
    "Tools: list_services, start_service, stop_service, restart_service, enable/disable_service."
)

PROCESS_PROMPT = (
    "You are the Process Specialist.\n"
    "Responsibilities: Manage running processes.\n"
    "Tools: list_processes, get_process_info, kill_process."
)

NETWORK_PROMPT = (
    "You are the Network Specialist.\n"
    "Responsibilities: Network diagnostics and information.\n"
    "Tools: list_network_interfaces, list_open_ports, ping_host, dns_lookup."
)

DISK_PROMPT = (
    "You are the Disk Specialist.\n"
    "Responsibilities: Disk usage and partition information.\n"
    "Tools: list_disks, get_disk_usage."
)

USER_PROMPT = (
    "You are the User Specialist.\n"
    "Responsibilities: detailed user and group management.\n"
    "Tools: list_users, list_groups, create_user, delete_user, manage_group."
)

LOG_PROMPT = (
    "You are the Log Specialist.\n"
    "Responsibilities: View and analyze system and file logs.\n"
    "Tools: get_system_logs, tail_log_file."
)

CRON_PROMPT = (
    "You are the Cron Specialist.\n"
    "Responsibilities: Manage scheduled tasks and cron jobs.\n"
    "Tools: list_cron_jobs, add_cron_job, remove_cron_job."
)

FIREWALL_PROMPT = (
    "You are the Firewall Specialist.\n"
    "Responsibilities: Manage firewall rules.\n"
    "Tools: list_firewall_rules, allow_port, deny_port."
)

SSH_PROMPT = (
    "You are the SSH Specialist.\n"
    "Responsibilities: Manage SSH keys.\n"
    "Tools: list_ssh_keys, generate_ssh_key, add_ssh_key."
)


def create_agent(
    provider: str = DEFAULT_PROVIDER,
    model_id: str = DEFAULT_MODEL_ID,
    base_url: Optional[str] = DEFAULT_LLM_BASE_URL,
    api_key: Optional[str] = DEFAULT_LLM_API_KEY,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_config: str = DEFAULT_MCP_CONFIG,
    skills_directory: Optional[str] = DEFAULT_SKILLS_DIRECTORY,
    ssl_verify: bool = DEFAULT_SSL_VERIFY,
) -> Agent:
    agent_toolsets = []

    if mcp_url:
        if "sse" in mcp_url.lower():
            server = MCPServerSSE(
                mcp_url,
                http_client=httpx.AsyncClient(
                    verify=ssl_verify, timeout=DEFAULT_TIMEOUT
                ),
            )
        else:
            server = MCPServerStreamableHTTP(
                mcp_url,
                http_client=httpx.AsyncClient(
                    verify=ssl_verify, timeout=DEFAULT_TIMEOUT
                ),
            )
        agent_toolsets.append(server)
        logger.info(f"Connected to MCP Server: {mcp_url}")
    elif mcp_config:
        mcp_toolset = load_mcp_servers(mcp_config)
        for server in mcp_toolset:
            if hasattr(server, "http_client"):
                server.http_client = httpx.AsyncClient(
                    verify=ssl_verify, timeout=DEFAULT_TIMEOUT
                )
        agent_toolsets.extend(mcp_toolset)
        logger.info(f"Connected to MCP Config JSON: {mcp_toolset}")

    model = create_model(
        provider=provider,
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        ssl_verify=ssl_verify,
        timeout=DEFAULT_TIMEOUT,
    )

    logger.info("Initializing Agents...")

    settings = ModelSettings(
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=DEFAULT_TEMPERATURE,
        top_p=DEFAULT_TOP_P,
        timeout=DEFAULT_TIMEOUT,
        parallel_tool_calls=DEFAULT_PARALLEL_TOOL_CALLS,
        seed=DEFAULT_SEED,
        presence_penalty=DEFAULT_PRESENCE_PENALTY,
        frequency_penalty=DEFAULT_FREQUENCY_PENALTY,
        logit_bias=DEFAULT_LOGIT_BIAS,
        stop_sequences=DEFAULT_STOP_SEQUENCES,
        extra_headers=DEFAULT_EXTRA_HEADERS,
        extra_body=DEFAULT_EXTRA_BODY,
    )

    # Define Agent Definitions: (Tag, Prompt, AgentName)
    agent_defs = {
        "system_management": (SYSTEM_PROMPT, "System_Specialist"),
        "filesystem": (FILESYSTEM_PROMPT, "Filesystem_Specialist"),
        "shell_management": (SHELL_PROMPT, "Shell_Specialist"),
        "python_management": (PYTHON_PROMPT, "Python_Specialist"),
        "node_management": (NODE_PROMPT, "Node_Specialist"),
        "service_management": (SERVICE_PROMPT, "Service_Specialist"),
        "process_management": (PROCESS_PROMPT, "Process_Specialist"),
        "network_management": (NETWORK_PROMPT, "Network_Specialist"),
        "disk_management": (DISK_PROMPT, "Disk_Specialist"),
        "user_management": (USER_PROMPT, "User_Specialist"),
        "log_management": (LOG_PROMPT, "Log_Specialist"),
        "cron_management": (CRON_PROMPT, "Cron_Specialist"),
        "firewall_management": (FIREWALL_PROMPT, "Firewall_Specialist"),
        "ssh_management": (SSH_PROMPT, "SSH_Specialist"),
    }

    child_agents = {}

    # Import filter_tools_by_tag here to avoid circular imports if any,
    # though it should be fine as it is in utils.
    from systems_manager.utils import filter_tools_by_tag

    class FilteredToolset:
        def __init__(self, original_toolset: Any, tag: str):
            self.original = original_toolset
            self.tag = tag

        @property
        def tools(self):
            # Inspect the original toolset for tools
            if hasattr(self.original, "tools"):
                original_tools = self.original.tools
                if callable(original_tools):
                    original_tools = original_tools()
                return filter_tools_by_tag(original_tools, self.tag)
            return []

    for tag, (prompt, name) in agent_defs.items():
        tag_toolsets = []
        # Filter MCP tools
        for ts in agent_toolsets:
            tag_toolsets.append(FilteredToolset(ts, tag))

        # Load specific skills
        if skills_directory:
            skill_dir_path = os.path.join(
                skills_directory, f"systems-manager-{tag.replace('_', '-')}"
            )
            if os.path.exists(skill_dir_path):
                tag_toolsets.append(SkillsToolset(directories=[skill_dir_path]))

        agent = Agent(
            name=name,
            system_prompt=prompt,
            model=model,
            model_settings=settings,
            toolsets=tag_toolsets,
            tool_timeout=DEFAULT_TOOL_TIMEOUT,
        )
        child_agents[tag] = agent

    supervisor = Agent(
        name=AGENT_NAME,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        model=model,
        model_settings=settings,
        deps_type=Any,
    )

    @supervisor.tool
    async def call_specialist(ctx: Any, tool_tag: str, request: str) -> str:
        """
        Delegates a task to a specialist agent.

        Args:
            tool_tag: The tag of the specialist to call (e.g., 'filesystem', 'python_management').
            request: The specific request for the specialist.
        """
        if tool_tag not in child_agents:
            return f"Error: No specialist found for tag '{tool_tag}'. Available: {list(child_agents.keys())}"

        agent = child_agents[tool_tag]
        # We need to run the agent.
        # usage: await agent.run(request)
        result = await agent.run(request)
        return result.data

    return supervisor


def create_agent_server(
    provider: str = DEFAULT_PROVIDER,
    model_id: str = DEFAULT_MODEL_ID,
    base_url: Optional[str] = DEFAULT_LLM_BASE_URL,
    api_key: Optional[str] = DEFAULT_LLM_API_KEY,
    mcp_url: str = DEFAULT_MCP_URL,
    mcp_config: str = DEFAULT_MCP_CONFIG,
    skills_directory: Optional[str] = DEFAULT_SKILLS_DIRECTORY,
    debug: Optional[bool] = DEFAULT_DEBUG,
    host: Optional[str] = DEFAULT_HOST,
    port: Optional[int] = DEFAULT_PORT,
    enable_web_ui: bool = DEFAULT_ENABLE_WEB_UI,
    ssl_verify: bool = DEFAULT_SSL_VERIFY,
):
    print(
        f"Starting {AGENT_NAME}:"
        f"\tprovider={provider}"
        f"\tmodel={model_id}"
        f"\tbase_url={base_url}"
        f"\tmcp={mcp_url} | {mcp_config}"
        f"\tssl_verify={ssl_verify}"
    )
    agent = create_agent(
        provider=provider,
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        mcp_url=mcp_url,
        mcp_config=mcp_config,
        skills_directory=skills_directory,
        ssl_verify=ssl_verify,
    )

    if skills_directory and os.path.exists(skills_directory):
        skills = load_skills_from_directory(skills_directory)
        logger.info(f"Loaded {len(skills)} skills from {skills_directory}")
    else:
        skills = [
            Skill(
                id="systems_manager_agent",
                name="Systems Manager Agent",
                description="General access to Systems Manager tools",
                tags=["sysadmin", "os"],
                input_modes=["text"],
                output_modes=["text"],
            )
        ]

    a2a_app = agent.to_a2a(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        version=__version__,
        skills=skills,
        debug=debug,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if hasattr(a2a_app, "router") and hasattr(a2a_app.router, "lifespan_context"):
            async with a2a_app.router.lifespan_context(a2a_app):
                yield
        else:
            yield

    app = FastAPI(
        title=f"{AGENT_NAME} - A2A + AG-UI Server",
        description=AGENT_DESCRIPTION,
        debug=debug,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health_check():
        return {"status": "OK"}

    app.mount("/a2a", a2a_app)

    @app.post("/ag-ui")
    async def ag_ui_endpoint(request: Request) -> Response:
        accept = request.headers.get("accept", SSE_CONTENT_TYPE)
        try:
            run_input = AGUIAdapter.build_run_input(await request.body())
        except ValidationError as e:
            return Response(
                content=json.dumps(e.json()),
                media_type="application/json",
                status_code=422,
            )

        if hasattr(run_input, "messages"):
            run_input.messages = prune_large_messages(run_input.messages)

        adapter = AGUIAdapter(agent=agent, run_input=run_input, accept=accept)
        event_stream = adapter.run_stream()
        sse_stream = adapter.encode_stream(event_stream)

        return StreamingResponse(
            sse_stream,
            media_type=accept,
        )

    if enable_web_ui:
        logger.info("Mounting Web UI")
        web_ui = agent.to_web(instructions=AGENT_SYSTEM_PROMPT)
        app.mount("/", web_ui)

    logger.info(
        "Starting server on %s:%s (A2A at /a2a, AG-UI at /ag-ui, Web UI: %s)",
        host,
        port,
        "Enabled at /" if enable_web_ui else "Disabled",
    )

    uvicorn.run(
        app,
        host=host,
        port=port,
        timeout_keep_alive=1800,
        timeout_graceful_shutdown=60,
        log_level="debug" if debug else "info",
    )


def agent_server():
    print(f"systems_manager_agent v{__version__}")
    parser = argparse.ArgumentParser(
        add_help=False, description=f"Run the {AGENT_NAME} A2A + AG-UI Server"
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to bind the server to"
    )
    parser.add_argument("--debug", type=bool, default=DEFAULT_DEBUG, help="Debug mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        choices=["openai", "anthropic", "google", "huggingface"],
        help="LLM Provider",
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="LLM Model ID")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_LLM_BASE_URL,
        help="LLM Base URL (for OpenAI compatible providers)",
    )
    parser.add_argument("--api-key", default=DEFAULT_LLM_API_KEY, help="LLM API Key")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL, help="MCP Server URL")
    parser.add_argument(
        "--mcp-config", default=DEFAULT_MCP_CONFIG, help="MCP Server Config"
    )
    parser.add_argument(
        "--skills-directory",
        default=DEFAULT_SKILLS_DIRECTORY,
        help="Directory containing agent skills",
    )

    parser.add_argument(
        "--web",
        action="store_true",
        default=DEFAULT_ENABLE_WEB_UI,
        help="Enable Pydantic AI Web UI",
    )

    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL verification for LLM requests (Use with caution)",
    )

    parser.add_argument("--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if hasattr(args, "help") and args.help:

        usage()

        sys.exit(0)

    if args.debug:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
            force=True,
        )
        logging.getLogger("pydantic_ai").setLevel(logging.DEBUG)
        logging.getLogger("fastmcp").setLevel(logging.DEBUG)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    create_agent_server(
        provider=args.provider,
        model_id=args.model_id,
        base_url=args.base_url,
        api_key=args.api_key,
        mcp_url=args.mcp_url,
        mcp_config=args.mcp_config,
        skills_directory=args.skills_directory,
        debug=args.debug,
        host=args.host,
        port=args.port,
        enable_web_ui=args.web,
        ssl_verify=not args.insecure,
    )


def usage():
    print(
        f"Systems Manager ({__version__}): CLI Tool\n\n"
        "Usage:\n"
        "--host                [ Host to bind the server to ]\n"
        "--port                [ Port to bind the server to ]\n"
        "--debug               [ Debug mode ]\n"
        "--reload              [ Enable auto-reload ]\n"
        "--provider            [ LLM Provider ]\n"
        "--model-id            [ LLM Model ID ]\n"
        "--base-url            [ LLM Base URL (for OpenAI compatible providers) ]\n"
        "--api-key             [ LLM API Key ]\n"
        "--mcp-url             [ MCP Server URL ]\n"
        "--mcp-config          [ MCP Server Config ]\n"
        "--skills-directory    [ Directory containing agent skills ]\n"
        "--web                 [ Enable Pydantic AI Web UI ]\n"
        "\n"
        "Examples:\n"
        "  [Simple]  systems-manager-agent \n"
        '  [Complex] systems-manager-agent --host "value" --port "value" --debug "value" --reload --provider "value" --model-id "value" --base-url "value" --api-key "value" --mcp-url "value" --mcp-config "value" --skills-directory "value" --web\n'
    )


if __name__ == "__main__":
    agent_server()
