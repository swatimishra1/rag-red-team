"""
Quick one-off script: lists every model your GROQ_API_KEY currently has
access to. Run this locally (network to api.groq.com isn't available from
this sandbox) to get the exact, current model ID to use.

Usage:
    export GROQ_API_KEY=your-key-here      # or $env:GROQ_API_KEY="..." on PowerShell
    python list_groq_models.py
"""
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

models = client.models.list()
print("Models available to your key:\n")
for m in sorted(models.data, key=lambda x: x.id):
    print(f"  {m.id}")
