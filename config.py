"""
Configuration module for Sage AI (Lunar Engine).
Manages paths, model settings, provider credentials, and fallback routing policies.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if available
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# App Constants
APP_NAME = "Sage AI"
APP_SUBTITLE = "Multi-Agentic AI Architecture"
APP_TAGLINE = "Plan • Create • Code • Automate • Anything"
APP_ID = "com.sageai.multiagent"

# Directories
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "sage_ai.db"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
WORKSPACE_ROOT = BASE_DIR / "workspace"
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

# UI Theme Constants
THEME_DARK_EMERALD = {
    "bg_window": "#080b16",
    "bg_surface": "#0a0e19",
    "bg_card_user": "#0e1b2c",
    "bg_card_assistant": "#111627",
    "bg_card_hover": "#141c33",
    "accent_primary": "#0FE6B5",
    "accent_secondary": "#0CC99D",
    "accent_glow": "rgba(15, 230, 181, 0.22)",
    "accent_subtle": "rgba(15, 230, 181, 0.08)",
    "text_primary": "#f4f5fb",
    "text_muted": "#a8afc2",
    "text_dim": "#626c85",
    "border_color": "rgba(15, 230, 181, 0.15)",
    "border_active": "#0FE6B5",
    "error_color": "#ff5c77",
    "warning_color": "#ffb84d",
    "success_color": "#0FE6B5",
}

# Model Provider Defaults
DEFAULT_MODELS = {
    "openrouter_coder": os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-coder-32b-instruct:free"),
    "groq_chat": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    "nvidia_chat": os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct"),
    "gemini_chat": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    "mistral_chat": os.getenv("MISTRAL_MODEL", "mistral-large-latest"),
    "cerebras_chat": os.getenv("CEREBRAS_MODEL", "llama-3.3-70b"),
    "cohere_chat": os.getenv("COHERE_MODEL", "command-r-plus-08-2024"),
    "huggingface_chat": os.getenv("HUGGINGFACE_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
    "cloudflare_chat": os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct"),
    "ollama_coder": os.getenv("OLLAMA_CODER_MODEL", "qwen3:8b"),
    "ollama_chat": os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b"),
    "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    "sd_base_url": os.getenv("SD_BASE_URL", "http://127.0.0.1:7860"),
    "image_model": os.getenv("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"),
    "image_free_credits": int(os.getenv("IMAGE_FREE_CREDITS", "25")),
    "tavily_api_url": "https://api.tavily.com/search",
}

# Curated Preset Models per Provider for User Selection (100% Free / Free-Tier)
PROVIDER_PRESET_MODELS = {
    "nvidia": [
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "nvidia/nemotron-4-340b-instruct",
        "mistralai/mixtral-8x7b-instruct-v0.1",
        "mistralai/mistral-large-2407",
        "deepseek-ai/deepseek-r1",
        "qwen/qwen2.5-72b-instruct",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-3.2-11b-vision-preview",
        "llama-3.2-90b-vision-preview",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b",
    ],
    "cerebras": [
        "llama-3.3-70b",
        "llama3.1-8b",
        "llama-3.1-70b",
    ],
    "mistral": [
        "mistral-large-latest",
        "codestral-latest",
        "mistral-small-latest",
        "open-mistral-7b",
        "open-mixtral-8x7b",
    ],
    "cloudflare": [
        "@cf/meta/llama-3.3-70b-instruct",
        "@cf/meta/llama-3.1-8b-instruct",
        "@cf/mistral/mistral-7b-instruct-v0.1",
        "@cf/qwen/qwen2.5-72b-instruct",
    ],
    "cohere": [
        "command-r-plus-08-2024",
        "command-r-08-2024",
        "command",
        "command-light",
    ],
    "huggingface": [
        "meta-llama/Llama-3.3-70B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
    ],
    "gemini": [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ],
    "openrouter": [
        "deepseek/deepseek-r1:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
        "deepseek/deepseek-chat:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "mistralai/mistral-small-24b-instruct-2501:free",
    ],
    "ollama": [
        "qwen2.5-coder:7b",
        "deepseek-r1:8b",
        "qwen3:8b",
        "llama3.2:3b",
        "llama3.1:8b",
        "mistral:7b",
        "codellama:7b",
    ],
}

# Provider Waterfall Chains
FALLBACK_CHAINS = {
    "coding": ["openrouter", "groq", "nvidia", "mistral", "cerebras", "gemini", "huggingface", "ollama_coder", "local_fallback"],
    "general_chat": ["groq", "cerebras", "nvidia", "mistral", "cloudflare", "cohere", "gemini", "huggingface", "openrouter", "ollama_chat", "local_fallback"],
    "web_search": ["tavily", "duckduckgo", "local_fallback"],
    "github_research": ["github_api", "web_search", "general_chat"],
    "image_generation": ["black_forest_flux", "local_canvas"],
    "local_facts": ["local_facts_provider"],
}

# Request Analysis Intent Categories
INTENT_CODING = "Coding/App"
INTENT_WEB_SEARCH = "Web Search"
INTENT_GITHUB = "GitHub Research"
INTENT_IMAGE = "Image Generation"
INTENT_LOCAL_FACTS = "Local Facts"
INTENT_GENERAL_CHAT = "General Chat"

ALL_INTENTS = [
    INTENT_CODING,
    INTENT_WEB_SEARCH,
    INTENT_GITHUB,
    INTENT_IMAGE,
    INTENT_LOCAL_FACTS,
    INTENT_GENERAL_CHAT,
]

# ==============================================================================
# Sage Multi-Agentic AI Architecture - Specialized Agent Definitions
# ==============================================================================
AGENT_RESEARCH = "Research Agent"
AGENT_CODING = "Coding Agent"
AGENT_IMAGE_MEDIA = "Image / Media Agent"
AGENT_DATA_ANALYSIS = "Data Analysis Agent"
AGENT_CONTENT = "Content Agent"
AGENT_EXECUTION = "Execution Agent"
AGENT_PLANNING = "Planning Agent"

ALL_AGENTS = [
    AGENT_RESEARCH,
    AGENT_CODING,
    AGENT_IMAGE_MEDIA,
    AGENT_DATA_ANALYSIS,
    AGENT_CONTENT,
    AGENT_EXECUTION,
    AGENT_PLANNING,
]

# Specialized Agent Metadata matching the Architecture Blueprint
AGENT_METADATA = {
    AGENT_RESEARCH: {
        "id": "research",
        "icon": "🔍",
        "color": "#38bdf8",  # Sky Blue
        "bg_color": "rgba(56, 189, 248, 0.12)",
        "tagline": "Information & Web Intelligence",
        "capabilities": [
            "Web search",
            "Gather information",
            "Read documents",
            "Summarize research"
        ]
    },
    AGENT_CODING: {
        "id": "coding",
        "icon": "</>",
        "color": "#0FE6B5",  # Neon Emerald
        "bg_color": "rgba(15, 230, 181, 0.12)",
        "tagline": "Software Engineering & Systems",
        "capabilities": [
            "Write / Debug code",
            "Create full projects",
            "Refactor & test",
            "Handle multiple files",
            "Use frameworks",
            "Deploy applications"
        ]
    },
    AGENT_IMAGE_MEDIA: {
        "id": "image_media",
        "icon": "🖼️",
        "color": "#fbbf24",  # Warm Amber
        "bg_color": "rgba(251, 191, 36, 0.12)",
        "tagline": "Visuals, UI/UX & Media Design",
        "capabilities": [
            "Generate images",
            "Edit images",
            "Create diagrams",
            "Design UI/UX",
            "Generate videos (if supported)",
            "Create charts & visuals"
        ]
    },
    AGENT_DATA_ANALYSIS: {
        "id": "data_analysis",
        "icon": "📊",
        "color": "#a855f7",  # Vibrant Purple
        "bg_color": "rgba(168, 85, 247, 0.12)",
        "tagline": "Insights, Data & Statistics",
        "capabilities": [
            "Analyze data",
            "Create charts",
            "Find insights",
            "Work with CSV/Excel",
            "Statistical analysis",
            "Generate reports"
        ]
    },
    AGENT_CONTENT: {
        "id": "content",
        "icon": "📑",
        "color": "#fb7185",  # Coral Rose
        "bg_color": "rgba(251, 113, 133, 0.12)",
        "tagline": "Writing, Documentation & Communication",
        "capabilities": [
            "Write articles",
            "Create documentation",
            "Generate presentations",
            "Prepare emails",
            "Summarize content",
            "Multi-language support"
        ]
    },
    AGENT_EXECUTION: {
        "id": "execution",
        "icon": "⚙️",
        "color": "#2dd4bf",  # Teal Cyan
        "bg_color": "rgba(45, 212, 191, 0.12)",
        "tagline": "Automation, Tools & Deployment",
        "capabilities": [
            "Run commands",
            "Use tools & APIs",
            "Manage files/folders",
            "Automate workflows",
            "Schedule tasks",
            "Deploy & monitor"
        ]
    },
    AGENT_PLANNING: {
        "id": "planning",
        "icon": "📅",
        "color": "#f97316",  # Sun Orange
        "bg_color": "rgba(249, 115, 22, 0.12)",
        "tagline": "Strategy, Milestones & Coordination",
        "capabilities": [
            "Plan complex tasks",
            "Set milestones",
            "Track progress",
            "Manage resources",
            "Adjust strategy",
            "Ensure completion"
        ]
    },
}

# Task & Workflow Lifecycle Statuses
TASK_STATUS_PENDING = "pending"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_RETRYING = "retrying"

