import os
from openai import OpenAI

api_key = os.getenv("GROQ_API_KEY", "your_groq_api_key")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)

print("Fetching ALL available models for this API key on Groq...")
try:
    models = client.models.list()
    available = [m.id for m in models.data]
    print(f"Total models found: {len(available)}")
    for m in available:
        print(f" - {m}")
except Exception as e:
    print(f"Error testing API key: {e}")
