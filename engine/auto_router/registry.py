"""
Universal Model Registry for Sage AI Auto Router.
Manages metadata, benchmarks, context windows, and task capabilities for all 54 registered models.
"""
from typing import Dict, List, Any, Optional
from database.db_manager import get_db
from .models import ModelSpec, TaskType


# Built-in specification catalog of all 54 core models
CORE_MODEL_SPECS: List[ModelSpec] = [
    # --------------------------------------------------------------------------
    # 1. Google Gemini (4 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        provider_id="gemini",
        base_quality=8.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.0,
            TaskType.CODING.value: 8.5,
            TaskType.REASONING.value: 8.8,
            TaskType.VISION.value: 9.5,
            TaskType.FAST_LIGHTWEIGHT.value: 9.4,
            TaskType.LONG_CONTEXT.value: 9.9,
            TaskType.AGENT.value: 9.0,
        },
        context_length=1048576,
        speed_score=9.4,
        is_free=True,
        description="Ultra-fast, million-token context multimodal flash model"
    ),
    ModelSpec(
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider_id="gemini",
        base_quality=9.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.3,
            TaskType.REASONING.value: 9.6,
            TaskType.VISION.value: 9.8,
            TaskType.FAST_LIGHTWEIGHT.value: 7.8,
            TaskType.LONG_CONTEXT.value: 10.0,
            TaskType.AGENT.value: 9.5,
        },
        context_length=2097152,
        speed_score=8.0,
        is_free=True,
        description="Two-million token context flagship frontier reasoning model"
    ),
    ModelSpec(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider_id="gemini",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.2,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 9.7,
            TaskType.FAST_LIGHTWEIGHT.value: 9.6,
            TaskType.LONG_CONTEXT.value: 9.9,
            TaskType.AGENT.value: 9.4,
        },
        context_length=1048576,
        speed_score=9.5,
        is_free=True,
        description="Next-gen real-time multimodal reasoning & coding speed"
    ),
    ModelSpec(
        model_id="gemini-2.0-flash-lite",
        display_name="Gemini 2.0 Flash Lite",
        provider_id="gemini",
        base_quality=8.7,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.8,
            TaskType.CODING.value: 8.4,
            TaskType.REASONING.value: 8.6,
            TaskType.VISION.value: 9.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.9,
            TaskType.LONG_CONTEXT.value: 9.8,
            TaskType.AGENT.value: 8.8,
        },
        context_length=1048576,
        speed_score=9.8,
        is_free=True,
        description="High-efficiency lightweight model with low latency"
    ),

    # --------------------------------------------------------------------------
    # 2. Groq Cloud (7 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B Versatile",
        provider_id="groq",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.0,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 6.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.8,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.2,
        },
        context_length=128000,
        speed_score=9.8,
        is_free=True,
        description="Ultra-fast LPU inference on state-of-the-art 70B model"
    ),
    ModelSpec(
        model_id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B Instant",
        provider_id="groq",
        base_quality=8.0,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.3,
            TaskType.CODING.value: 7.8,
            TaskType.REASONING.value: 7.9,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 10.0,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.0,
        },
        context_length=128000,
        speed_score=10.0,
        is_free=True,
        description="Blazing 800+ tokens/sec instant completion on Groq LPU"
    ),
    ModelSpec(
        model_id="llama-3.2-11b-vision-preview",
        display_name="Llama 3.2 11B Vision",
        provider_id="groq",
        base_quality=8.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.4,
            TaskType.CODING.value: 7.9,
            TaskType.REASONING.value: 8.2,
            TaskType.VISION.value: 9.2,
            TaskType.FAST_LIGHTWEIGHT.value: 9.6,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.4,
        },
        context_length=128000,
        speed_score=9.6,
        is_free=True,
        supports_vision=True,
        description="High-speed multimodal vision on Groq LPU"
    ),
    ModelSpec(
        model_id="llama-3.2-90b-vision-preview",
        display_name="Llama 3.2 90B Vision",
        provider_id="groq",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.1,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 9.7,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=128000,
        speed_score=9.2,
        is_free=True,
        supports_vision=True,
        description="Flagship 90B multimodal vision reasoning on Groq LPU"
    ),
    ModelSpec(
        model_id="mixtral-8x7b-32768",
        display_name="Mixtral 8x7B MoE",
        provider_id="groq",
        base_quality=8.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.7,
            TaskType.CODING.value: 8.5,
            TaskType.REASONING.value: 8.6,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.4,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.6,
        },
        context_length=32768,
        speed_score=9.5,
        is_free=True,
        description="Sparse Mixture-of-Experts high-throughput model"
    ),
    ModelSpec(
        model_id="gemma2-9b-it",
        display_name="Gemma 2 9B Instruct",
        provider_id="groq",
        base_quality=8.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.4,
            TaskType.CODING.value: 7.9,
            TaskType.REASONING.value: 8.6,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.7,
            TaskType.LONG_CONTEXT.value: 7.0,
            TaskType.AGENT.value: 8.2,
        },
        context_length=8192,
        speed_score=9.7,
        is_free=True,
        description="Google Gemma 2 compact architectural reasoning model"
    ),
    ModelSpec(
        model_id="deepseek-r1-distill-llama-70b",
        display_name="DeepSeek R1 Distill 70B",
        provider_id="groq",
        base_quality=9.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.5,
            TaskType.REASONING.value: 9.9,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.4,
        },
        context_length=128000,
        speed_score=9.0,
        is_free=True,
        description="DeepSeek R1 chain-of-thought distilled into Llama 70B on Groq"
    ),

    # --------------------------------------------------------------------------
    # 3. OpenRouter (6 Core Free Presets + Dynamic)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="deepseek/deepseek-r1",
        display_name="DeepSeek R1 Reasoning",
        provider_id="openrouter",
        base_quality=9.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.7,
            TaskType.REASONING.value: 10.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 7.5,
            TaskType.LONG_CONTEXT.value: 9.2,
            TaskType.AGENT.value: 9.6,
        },
        context_length=128000,
        speed_score=7.6,
        is_free=False,
        description="Premier full-scale chain-of-thought mathematical reasoning model"
    ),
    ModelSpec(
        model_id="qwen/qwen-2.5-coder-32b-instruct",
        display_name="Qwen 2.5 Coder 32B",
        provider_id="openrouter",
        base_quality=9.7,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.2,
            TaskType.CODING.value: 10.0,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.6,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 9.5,
        },
        context_length=32768,
        speed_score=8.6,
        is_free=False,
        description="World-class coding specialist benchmarked against Claude 3.5 Sonnet"
    ),
    ModelSpec(
        model_id="deepseek/deepseek-chat",
        display_name="DeepSeek V3 Chat",
        provider_id="openrouter",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.5,
            TaskType.CODING.value: 9.2,
            TaskType.REASONING.value: 9.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 8.8,
            TaskType.AGENT.value: 9.2,
        },
        context_length=64000,
        speed_score=8.8,
        is_free=False,
        description="General multi-domain flagship conversational model"
    ),
    ModelSpec(
        model_id="meta-llama/llama-3.3-70b-instruct",
        display_name="Llama 3.3 70B Instruct",
        provider_id="openrouter",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.0,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.4,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.1,
        },
        context_length=128000,
        speed_score=8.4,
        is_free=False,
        description="Meta's frontier open-weights instruction-tuned 70B model"
    ),
    ModelSpec(
        model_id="deepseek/deepseek-v4-flash-0731:free",
        display_name="DeepSeek V4 Flash (Free)",
        provider_id="openrouter",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.2,
            TaskType.CODING.value: 9.3,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.5,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=128000,
        speed_score=9.4,
        is_free=True,
        description="OpenRouter active free tier high-speed reasoning and coding model"
    ),
    ModelSpec(
        model_id="google/gemini-2.0-flash-exp:free",
        display_name="Gemini 2.0 Flash Exp (Free)",
        provider_id="openrouter",
        base_quality=9.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.3,
            TaskType.REASONING.value: 9.5,
            TaskType.VISION.value: 9.7,
            TaskType.FAST_LIGHTWEIGHT.value: 9.2,
            TaskType.LONG_CONTEXT.value: 10.0,
            TaskType.AGENT.value: 9.5,
        },
        context_length=1048576,
        speed_score=9.1,
        is_free=True,
        supports_vision=True,
        description="Experimental million-token next-gen multimodal model"
    ),
    ModelSpec(
        model_id="mistralai/mistral-small-24b-instruct-2501:free",
        display_name="Mistral Small 24B (Free)",
        provider_id="openrouter",
        base_quality=8.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.0,
            TaskType.CODING.value: 8.9,
            TaskType.REASONING.value: 8.9,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.9,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.9,
        },
        context_length=32768,
        speed_score=8.9,
        is_free=True,
        description="Mistral AI's compact high-efficiency instruction model"
    ),

    # --------------------------------------------------------------------------
    # 4. NVIDIA NIM (10 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="meta/llama-3.2-11b-vision-instruct",
        display_name="NVIDIA Llama 3.2 11B Vision",
        provider_id="nvidia",
        base_quality=8.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.5,
            TaskType.CODING.value: 8.0,
            TaskType.REASONING.value: 8.3,
            TaskType.VISION.value: 9.4,
            TaskType.FAST_LIGHTWEIGHT.value: 9.2,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.6,
        },
        context_length=128000,
        speed_score=9.2,
        is_free=True,
        supports_vision=True,
        description="NVIDIA NIM accelerated vision-language pipeline"
    ),
    ModelSpec(
        model_id="meta/llama-3.1-70b-instruct",
        display_name="NVIDIA Llama 3.1 70B",
        provider_id="nvidia",
        base_quality=9.0,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.1,
            TaskType.CODING.value: 8.8,
            TaskType.REASONING.value: 9.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.6,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.0,
        },
        context_length=128000,
        speed_score=8.6,
        is_free=True,
        description="Enterprise TensorRT-LLM optimized Llama 70B"
    ),
    ModelSpec(
        model_id="meta/llama-3.1-8b-instruct",
        display_name="NVIDIA Llama 3.1 8B",
        provider_id="nvidia",
        base_quality=7.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.2,
            TaskType.CODING.value: 7.7,
            TaskType.REASONING.value: 7.8,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.8,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.0,
        },
        context_length=128000,
        speed_score=9.8,
        is_free=True,
        description="High-speed edge-optimized 8B model on NVIDIA NIM"
    ),
    ModelSpec(
        model_id="meta/llama-3.3-70b-instruct",
        display_name="NVIDIA Llama 3.3 70B",
        provider_id="nvidia",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.0,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.7,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.2,
        },
        context_length=128000,
        speed_score=8.7,
        is_free=True,
        description="Flagship open-weights instruction model with TensorRT speed"
    ),
    ModelSpec(
        model_id="nvidia/llama-3.1-nemotron-70b-instruct",
        display_name="NVIDIA Nemotron 70B",
        provider_id="nvidia",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.1,
            TaskType.REASONING.value: 9.6,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.5,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=128000,
        speed_score=8.5,
        is_free=True,
        description="NVIDIA aligned frontier model with superior reasoning capability"
    ),
    ModelSpec(
        model_id="nvidia/nemotron-4-340b-instruct",
        display_name="NVIDIA Nemotron 340B",
        provider_id="nvidia",
        base_quality=9.5,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.5,
            TaskType.CODING.value: 9.3,
            TaskType.REASONING.value: 9.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 7.0,
            TaskType.LONG_CONTEXT.value: 6.5,
            TaskType.AGENT.value: 9.4,
        },
        context_length=4096,
        speed_score=7.0,
        is_free=True,
        description="Massive 340B parameter dense enterprise intelligence engine"
    ),
    ModelSpec(
        model_id="mistralai/mixtral-8x7b-instruct-v0.1",
        display_name="NVIDIA Mixtral 8x7B",
        provider_id="nvidia",
        base_quality=8.5,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.6,
            TaskType.CODING.value: 8.4,
            TaskType.REASONING.value: 8.5,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.5,
        },
        context_length=32768,
        speed_score=9.0,
        is_free=True,
        description="Mixture-of-Experts routing on NVIDIA TensorRT microservices"
    ),
    ModelSpec(
        model_id="mistralai/mistral-large-2407",
        display_name="NVIDIA Mistral Large 2407",
        provider_id="nvidia",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.2,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.2,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=128000,
        speed_score=8.2,
        is_free=True,
        description="Mistral AI's flagship 123B model running on NVIDIA NIM"
    ),
    ModelSpec(
        model_id="deepseek-ai/deepseek-r1",
        display_name="NVIDIA DeepSeek R1",
        provider_id="nvidia",
        base_quality=9.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.7,
            TaskType.REASONING.value: 10.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 7.6,
            TaskType.LONG_CONTEXT.value: 9.2,
            TaskType.AGENT.value: 9.6,
        },
        context_length=128000,
        speed_score=7.6,
        is_free=True,
        description="DeepSeek R1 full reasoning model accelerated on NVIDIA Hopper"
    ),
    ModelSpec(
        model_id="qwen/qwen2.5-72b-instruct",
        display_name="NVIDIA Qwen 2.5 72B",
        provider_id="nvidia",
        base_quality=9.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.5,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.3,
            TaskType.LONG_CONTEXT.value: 8.8,
            TaskType.AGENT.value: 9.3,
        },
        context_length=32768,
        speed_score=8.3,
        is_free=True,
        description="Alibaba Qwen 2.5 72B with high coding and reasoning scores"
    ),

    # --------------------------------------------------------------------------
    # 5. Mistral AI (5 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="mistral-large-latest",
        display_name="Mistral Large",
        provider_id="mistral",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.4,
            TaskType.CODING.value: 9.2,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.2,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.4,
        },
        context_length=128000,
        speed_score=8.2,
        is_free=True,
        description="Mistral AI's top-tier multilingual flagship model"
    ),
    ModelSpec(
        model_id="codestral-latest",
        display_name="Codestral",
        provider_id="mistral",
        base_quality=9.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.9,
            TaskType.CODING.value: 10.0,
            TaskType.REASONING.value: 9.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 9.4,
        },
        context_length=32768,
        speed_score=8.8,
        is_free=True,
        description="Mistral AI dedicated coding specialist across 80+ programming languages"
    ),
    ModelSpec(
        model_id="mistral-small-latest",
        display_name="Mistral Small",
        provider_id="mistral",
        base_quality=8.7,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.8,
            TaskType.CODING.value: 8.6,
            TaskType.REASONING.value: 8.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.2,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.8,
        },
        context_length=32768,
        speed_score=9.2,
        is_free=True,
        description="Cost-effective, low-latency reasoning and summarization model"
    ),
    ModelSpec(
        model_id="open-mistral-7b",
        display_name="Mistral 7B",
        provider_id="mistral",
        base_quality=7.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.0,
            TaskType.CODING.value: 7.6,
            TaskType.REASONING.value: 7.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.6,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 7.8,
        },
        context_length=32768,
        speed_score=9.6,
        is_free=True,
        description="Pioneering 7B open architecture with sliding window attention"
    ),
    ModelSpec(
        model_id="open-mixtral-8x7b",
        display_name="Mixtral 8x7B",
        provider_id="mistral",
        base_quality=8.5,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.6,
            TaskType.CODING.value: 8.4,
            TaskType.REASONING.value: 8.5,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.1,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.5,
        },
        context_length=32768,
        speed_score=9.1,
        is_free=True,
        description="8-expert sparse mixture-of-experts model"
    ),

    # --------------------------------------------------------------------------
    # 6. Cerebras (Wafer-Scale) (3 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="llama-3.3-70b",
        display_name="Cerebras Llama 3.3 70B",
        provider_id="cerebras",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.0,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 10.0,
            TaskType.LONG_CONTEXT.value: 7.0,
            TaskType.AGENT.value: 9.2,
        },
        context_length=8192,
        speed_score=10.0,
        is_free=True,
        description="World's fastest inference on Cerebras CS-3 Wafer-Scale Engine"
    ),
    ModelSpec(
        model_id="llama3.1-8b",
        display_name="Cerebras Llama 3.1 8B",
        provider_id="cerebras",
        base_quality=7.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.2,
            TaskType.CODING.value: 7.7,
            TaskType.REASONING.value: 7.8,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 10.0,
            TaskType.LONG_CONTEXT.value: 7.0,
            TaskType.AGENT.value: 8.0,
        },
        context_length=8192,
        speed_score=10.0,
        is_free=True,
        description="1800+ tokens/sec record-shattering wafer-scale generation"
    ),
    ModelSpec(
        model_id="llama-3.1-70b",
        display_name="Cerebras Llama 3.1 70B",
        provider_id="cerebras",
        base_quality=9.0,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.1,
            TaskType.CODING.value: 8.8,
            TaskType.REASONING.value: 9.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 10.0,
            TaskType.LONG_CONTEXT.value: 7.0,
            TaskType.AGENT.value: 9.0,
        },
        context_length=8192,
        speed_score=10.0,
        is_free=True,
        description="Instantaneous 70B generation on custom wafer hardware"
    ),

    # --------------------------------------------------------------------------
    # 7. Cloudflare Workers AI (4 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="@cf/meta/llama-3.3-70b-instruct",
        display_name="Cloudflare Llama 3.3 70B",
        provider_id="cloudflare",
        base_quality=9.1,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.2,
            TaskType.CODING.value: 8.9,
            TaskType.REASONING.value: 9.1,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.1,
        },
        context_length=128000,
        speed_score=8.8,
        is_free=True,
        description="Global edge serverless inference across 300+ datacenters"
    ),
    ModelSpec(
        model_id="@cf/meta/llama-3.1-8b-instruct",
        display_name="Cloudflare Llama 3.1 8B",
        provider_id="cloudflare",
        base_quality=7.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.1,
            TaskType.CODING.value: 7.6,
            TaskType.REASONING.value: 7.8,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.6,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.0,
        },
        context_length=128000,
        speed_score=9.6,
        is_free=True,
        description="Ultra low-latency edge deployment with zero warm-up"
    ),
    ModelSpec(
        model_id="@cf/mistral/mistral-7b-instruct-v0.1",
        display_name="Cloudflare Mistral 7B",
        provider_id="cloudflare",
        base_quality=7.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.0,
            TaskType.CODING.value: 7.6,
            TaskType.REASONING.value: 7.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.5,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 7.8,
        },
        context_length=32768,
        speed_score=9.5,
        is_free=True,
        description="Edge-deployed Mistral 7B on Cloudflare Workers AI"
    ),
    ModelSpec(
        model_id="@cf/qwen/qwen2.5-72b-instruct",
        display_name="Cloudflare Qwen 2.5 72B",
        provider_id="cloudflare",
        base_quality=9.3,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.2,
            TaskType.CODING.value: 9.4,
            TaskType.REASONING.value: 9.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.6,
            TaskType.LONG_CONTEXT.value: 8.8,
            TaskType.AGENT.value: 9.2,
        },
        context_length=32768,
        speed_score=8.6,
        is_free=True,
        description="Serverless edge-accelerated Qwen 72B"
    ),

    # --------------------------------------------------------------------------
    # 8. Cohere (4 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="command-r-plus-08-2024",
        display_name="Cohere Command R+",
        provider_id="cohere",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 8.8,
            TaskType.REASONING.value: 9.2,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.4,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.8,
        },
        context_length=128000,
        speed_score=8.4,
        is_free=True,
        description="Enterprise RAG and tool-use optimization champion"
    ),
    ModelSpec(
        model_id="command-r-08-2024",
        display_name="Cohere Command R",
        provider_id="cohere",
        base_quality=8.7,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.8,
            TaskType.CODING.value: 8.4,
            TaskType.REASONING.value: 8.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=128000,
        speed_score=9.0,
        is_free=True,
        description="Fast enterprise agentic search and generation model"
    ),
    ModelSpec(
        model_id="command",
        display_name="Cohere Command",
        provider_id="cohere",
        base_quality=8.1,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.2,
            TaskType.CODING.value: 7.8,
            TaskType.REASONING.value: 8.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 6.0,
            TaskType.AGENT.value: 8.2,
        },
        context_length=4096,
        speed_score=8.8,
        is_free=True,
        description="Standard instruction tuned conversational model"
    ),
    ModelSpec(
        model_id="command-light",
        display_name="Cohere Command Light",
        provider_id="cohere",
        base_quality=7.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 7.9,
            TaskType.CODING.value: 7.3,
            TaskType.REASONING.value: 7.5,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.6,
            TaskType.LONG_CONTEXT.value: 6.0,
            TaskType.AGENT.value: 7.8,
        },
        context_length=4096,
        speed_score=9.6,
        is_free=True,
        description="Lightweight high-speed Cohere generation"
    ),

    # --------------------------------------------------------------------------
    # 9. Hugging Face (3 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="meta-llama/Llama-3.3-70B-Instruct",
        display_name="HF Llama 3.3 70B",
        provider_id="huggingface",
        base_quality=9.1,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.2,
            TaskType.CODING.value: 8.9,
            TaskType.REASONING.value: 9.1,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.2,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 9.1,
        },
        context_length=128000,
        speed_score=8.2,
        is_free=True,
        description="Serverless Hugging Face Inference API on Llama 3.3 70B"
    ),
    ModelSpec(
        model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
        display_name="HF Qwen 2.5 Coder 32B",
        provider_id="huggingface",
        base_quality=9.6,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.0,
            TaskType.CODING.value: 9.9,
            TaskType.REASONING.value: 9.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.2,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 9.4,
        },
        context_length=32768,
        speed_score=8.2,
        is_free=True,
        description="Hugging Face serverless coding specialist"
    ),
    ModelSpec(
        model_id="mistralai/Mistral-7B-Instruct-v0.3",
        display_name="HF Mistral 7B v0.3",
        provider_id="huggingface",
        base_quality=7.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.1,
            TaskType.CODING.value: 7.7,
            TaskType.REASONING.value: 7.8,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.2,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.0,
        },
        context_length=32768,
        speed_score=9.2,
        is_free=True,
        description="Mistral 7B v0.3 with native function calling on Hugging Face"
    ),

    # --------------------------------------------------------------------------
    # 10. Local Ollama (7 Models)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="qwen3:8b",
        display_name="Ollama Qwen 3 8B",
        provider_id="ollama",
        base_quality=8.5,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.6,
            TaskType.CODING.value: 8.8,
            TaskType.REASONING.value: 8.5,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.6,
        },
        context_length=32768,
        speed_score=8.8,
        is_free=True,
        description="Next-gen offline local assistant and coding model"
    ),
    ModelSpec(
        model_id="qwen2.5-coder:7b",
        display_name="Ollama Qwen 2.5 Coder 7B",
        provider_id="ollama",
        base_quality=8.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.3,
            TaskType.CODING.value: 9.3,
            TaskType.REASONING.value: 8.7,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.8,
        },
        context_length=32768,
        speed_score=8.8,
        is_free=True,
        description="Dedicated local offline coding powerhouse"
    ),
    ModelSpec(
        model_id="deepseek-r1:8b",
        display_name="Ollama DeepSeek R1 8B",
        provider_id="ollama",
        base_quality=8.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.6,
            TaskType.CODING.value: 8.8,
            TaskType.REASONING.value: 9.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.0,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 8.7,
        },
        context_length=32768,
        speed_score=8.0,
        is_free=True,
        description="Full local chain-of-thought reasoning without cloud connection"
    ),
    ModelSpec(
        model_id="llama3.2:3b",
        display_name="Ollama Llama 3.2 3B",
        provider_id="ollama",
        base_quality=7.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 7.7,
            TaskType.CODING.value: 7.0,
            TaskType.REASONING.value: 7.3,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.8,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 7.5,
        },
        context_length=128000,
        speed_score=9.8,
        is_free=True,
        description="Ultra-lightweight edge model with minimal RAM footprint"
    ),
    ModelSpec(
        model_id="llama3.1:8b",
        display_name="Ollama Llama 3.1 8B",
        provider_id="ollama",
        base_quality=8.0,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.2,
            TaskType.CODING.value: 7.8,
            TaskType.REASONING.value: 8.0,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 9.0,
            TaskType.AGENT.value: 8.1,
        },
        context_length=128000,
        speed_score=9.0,
        is_free=True,
        description="Versatile 128k context local offline model"
    ),
    ModelSpec(
        model_id="mistral:7b",
        display_name="Ollama Mistral 7B",
        provider_id="ollama",
        base_quality=7.8,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.0,
            TaskType.CODING.value: 7.7,
            TaskType.REASONING.value: 7.8,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 8.5,
            TaskType.AGENT.value: 7.9,
        },
        context_length=32768,
        speed_score=9.0,
        is_free=True,
        description="Classic high-speed offline local Mistral 7B"
    ),
    ModelSpec(
        model_id="codellama:7b",
        display_name="Ollama Code Llama 7B",
        provider_id="ollama",
        base_quality=8.1,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 7.6,
            TaskType.CODING.value: 8.6,
            TaskType.REASONING.value: 8.1,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 8.8,
            TaskType.LONG_CONTEXT.value: 7.5,
            TaskType.AGENT.value: 8.2,
        },
        context_length=16384,
        speed_score=8.8,
        is_free=True,
        description="Meta's dedicated code generation model running locally"
    ),

    # --------------------------------------------------------------------------
    # 11. Image Studio (1 Model)
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="black-forest-labs/FLUX.1-schnell",
        display_name="FLUX.1 Schnell (Diffusion)",
        provider_id="image",
        base_quality=9.8,
        task_capabilities={
            TaskType.IMAGE_GEN.value: 10.0,
            TaskType.VISION.value: 8.0,
            TaskType.GENERAL_CHAT.value: 5.0,
            TaskType.CODING.value: 5.0,
            TaskType.REASONING.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.0,
            TaskType.LONG_CONTEXT.value: 5.0,
            TaskType.AGENT.value: 7.0,
        },
        context_length=1024,
        speed_score=9.0,
        is_free=True,
        supports_vision=True,
        description="State-of-the-art 12-step rectified flow image synthesis"
    ),

    # --------------------------------------------------------------------------
    # 10. OpenRouter Frontier & Active Free Coding Models
    # --------------------------------------------------------------------------
    ModelSpec(
        model_id="unbiased/pareto",
        display_name="Pareto 26.9 (Union Alpha)",
        provider_id="openrouter",
        base_quality=9.9,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.6,
            TaskType.CODING.value: 10.0,
            TaskType.REASONING.value: 9.8,
            TaskType.VISION.value: 9.2,
            TaskType.FAST_LIGHTWEIGHT.value: 8.5,
            TaskType.LONG_CONTEXT.value: 9.8,
            TaskType.AGENT.value: 9.8,
        },
        context_length=262144,
        speed_score=8.7,
        is_free=False,
        cost_per_m_tokens=2.5,
        description="Pareto 26.9 (formerly stealth Union Alpha) - 262k context frontier coding SOTA"
    ),
    ModelSpec(
        model_id="deepseek/deepseek-v4-flash-0731:free",
        display_name="DeepSeek V4 Flash (Free)",
        provider_id="openrouter",
        base_quality=9.4,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 9.3,
            TaskType.CODING.value: 9.5,
            TaskType.REASONING.value: 9.4,
            TaskType.VISION.value: 8.5,
            TaskType.FAST_LIGHTWEIGHT.value: 9.8,
            TaskType.LONG_CONTEXT.value: 10.0,
            TaskType.AGENT.value: 9.3,
        },
        context_length=1000000,
        speed_score=9.6,
        is_free=True,
        description="Active 100% free 1M token context high-speed reasoning model on OpenRouter"
    ),
    ModelSpec(
        model_id="cohere/north-mini-code:free",
        display_name="Cohere North Mini Code (Free)",
        provider_id="openrouter",
        base_quality=9.2,
        task_capabilities={
            TaskType.GENERAL_CHAT.value: 8.8,
            TaskType.CODING.value: 9.4,
            TaskType.REASONING.value: 9.1,
            TaskType.VISION.value: 5.0,
            TaskType.FAST_LIGHTWEIGHT.value: 9.4,
            TaskType.LONG_CONTEXT.value: 9.4,
            TaskType.AGENT.value: 9.0,
        },
        context_length=256000,
        speed_score=9.3,
        is_free=True,
        description="Active 100% free 256k context dedicated coding model on OpenRouter"
    ),
]


class ModelRegistry:
    """Manages the catalog of all registered models with database synchronization."""

    _db_synced = False

    def __init__(self):
        self._models: Dict[str, ModelSpec] = {}
        self._initialize_registry()

    def _initialize_registry(self):
        """Populates registry with core models and syncs to SQLite via single batch."""
        for spec in CORE_MODEL_SPECS:
            self._models[spec.model_id] = spec

        if not ModelRegistry._db_synced:
            try:
                db = get_db()
                batch = [
                    {
                        "model_id": spec.model_id,
                        "display_name": spec.display_name,
                        "provider_id": spec.provider_id,
                        "base_quality": spec.base_quality,
                        "task_capabilities": spec.task_capabilities,
                        "context_length": spec.context_length,
                        "speed_score": spec.speed_score,
                        "is_free": spec.is_free,
                        "cost_per_m_tokens": spec.cost_per_m_tokens,
                        "description": spec.description
                    }
                    for spec in CORE_MODEL_SPECS
                ]
                db.upsert_registered_models_batch(batch)
            except Exception:
                pass
            ModelRegistry._db_synced = True

    def get_all_models(self) -> List[ModelSpec]:
        """Returns all registered models, including any dynamic local Ollama models."""
        models = list(self._models.values())
        
        # Discover any additional installed models from local Ollama
        try:
            from engine.ollama_manager import get_installed_ollama_models, is_ollama_running
            if is_ollama_running():
                installed = get_installed_ollama_models()
                for inst_name in installed:
                    if inst_name not in self._models:
                        is_coder = any(k in inst_name.lower() for k in ("coder", "code"))
                        is_r1 = "r1" in inst_name.lower()
                        dyn_spec = ModelSpec(
                            model_id=inst_name,
                            display_name=f"Ollama {inst_name}",
                            provider_id="ollama",
                            base_quality=8.4 if is_coder or is_r1 else 7.8,
                            task_capabilities={
                                TaskType.GENERAL_CHAT.value: 8.0,
                                TaskType.CODING.value: 9.0 if is_coder else 7.8,
                                TaskType.REASONING.value: 9.1 if is_r1 else 8.0,
                                TaskType.VISION.value: 5.0,
                                TaskType.FAST_LIGHTWEIGHT.value: 8.8,
                                TaskType.LONG_CONTEXT.value: 8.0,
                                TaskType.AGENT.value: 8.2,
                            },
                            context_length=32768,
                            speed_score=8.5,
                            is_free=True,
                            description=f"Installed local model in Ollama ({inst_name})"
                        )
                        models.append(dyn_spec)
        except Exception:
            pass

        return models

    def get_models_by_provider(self) -> Dict[str, List[ModelSpec]]:
        """Returns registered models grouped by provider_id."""
        grouped: Dict[str, List[ModelSpec]] = {}
        for m in self.get_all_models():
            grouped.setdefault(m.provider_id, []).append(m)
        return grouped

    def get_model(self, model_id: str) -> Optional[ModelSpec]:
        """Retrieves a ModelSpec by exact model ID or prefix match."""
        if model_id in self._models:
            return self._models[model_id]
        for mid, spec in self._models.items():
            if mid.lower() == model_id.lower() or model_id.lower() in mid.lower():
                return spec
        return None

    def register_custom_model(self, spec: ModelSpec):
        """Registers or overrides a model dynamically."""
        self._models[spec.model_id] = spec
        get_db().upsert_registered_model({
            "model_id": spec.model_id,
            "display_name": spec.display_name,
            "provider_id": spec.provider_id,
            "base_quality": spec.base_quality,
            "task_capabilities": spec.task_capabilities,
            "context_length": spec.context_length,
            "speed_score": spec.speed_score,
            "is_free": spec.is_free,
            "cost_per_m_tokens": spec.cost_per_m_tokens,
            "description": spec.description
        })
