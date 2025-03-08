from .siteconf_manager import load_config
from ollama import AsyncClient

config = load_config()
OLLAMA_ENDPOINT, DEFAULT_MODEL = config["ollama_endpoint"], config["default_model"]
client = AsyncClient(
    host=OLLAMA_ENDPOINT,
)

async def generate_chat_stream(message: str, context: list):
    """Chat with the Ollama model and return the response as a Server-Sent Event."""
    context.append({'role': 'user', 'content': message})

    stream = client.chat(
        model=DEFAULT_MODEL,
        messages=context,
        stream=True,
    )
    async for chunk in await stream:
        yield chunk.message.content
        context.append(chunk.message)
    return
