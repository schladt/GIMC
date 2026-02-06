from __future__ import annotations

import os
import sys
import json
import re
import requests
from typing import List, Dict, Optional

# add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import CHAT_ENDPOINT  


Message = Dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


class OllamaChat:
    def __init__(
        self,
        model: str = "llama3.1",
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        seed: Optional[int] = None,
        timeout_s: int = 120,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout_s = timeout_s

        self.messages: List[Message] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def chat(self, user_text: str, stream: bool = False) -> str:
        """Send a user message, append assistant reply to history, return the reply text."""
        self.messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
            },
        }
        if self.seed is not None:
            payload["options"]["seed"] = self.seed

        if not stream:
            r = requests.post(CHAT_ENDPOINT, json=payload, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
            reply = data["message"]["content"]
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        # Streaming mode: Ollama returns newline-delimited JSON objects
        reply_chunks: List[str] = []
        with requests.post(CHAT_ENDPOINT, json=payload, stream=True, timeout=self.timeout_s) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                obj = json.loads(line)
                if "message" in obj and "content" in obj["message"]:
                    chunk = obj["message"]["content"]
                    if chunk:
                        reply_chunks.append(chunk)
                        print(chunk, end="", flush=True)
                if obj.get("done"):
                    break
        print()  # newline after streaming output

        reply = "".join(reply_chunks)
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def parse_variants(content):
        """
        Parse variants from text content and extract source code and makefiles.
        
        Args:
            content: String containing LLM-generated variants
        
        Returns:
            List of dicts: [{'code': '...', 'makefile': '...', 'source_file': '...', 'makefile_file': '...'}, ...]
        """
        # Split into variants
        variant_blocks = re.split(r'===\s*VARIANT\s+\d+\s*===', content)
        
        variants = []
        
        for block in variant_blocks:
            if not block.strip():
                continue
            
            # Extract source code
            source_match = re.search(
                r'===\s*SOURCE:\s*(\S+)\s*===\s*```(?:c\+\+|cpp|c)?\s*\n(.*?)\n```',
                block,
                re.DOTALL
            )
            
            # Extract makefile
            makefile_match = re.search(
                r'===\s*MAKEFILE:\s*(\S+)\s*===\s*```(?:makefile|make)?\s*\n(.*?)\n```',
                block,
                re.DOTALL
            )
            
            if source_match and makefile_match:
                source_filename = source_match.group(1)
                source_code = source_match.group(2)
                
                makefile_filename = makefile_match.group(1)
                makefile_code = makefile_match.group(2)
                
                variants.append({
                    'code': source_code,
                    'makefile': makefile_code,
                    'source_file': source_filename,
                    'makefile_file': makefile_filename
                })
        
        return variants