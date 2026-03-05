from __future__ import annotations

import os
import sys
import json
import re
import requests
import base64
from typing import List, Dict, Optional

# add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from genetic_improvement.config import CHAT_ENDPOINT, SANDBOX_TOKEN, EVALUATION_SERVER


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
    
    def parse_repair(content):
        """
        Parse repaired code from LLM response.
        
        Args:
            content: String containing LLM-generated repair response
        
        Returns:
            Dict: {'code': '...', 'makefile': '...'} or None if parsing fails
        """
        # Look for === REPAIRED === section
        if '=== REPAIRED ===' not in content:
            print("DEBUG: '=== REPAIRED ===' marker not found in LLM response")
            print(f"DEBUG: Response preview (first 500 chars): {content[:500]}")
            return None
        
        # Extract source code
        source_match = re.search(
            r'===\s*SOURCE\s*===\s*```(?:c\+\+|cpp|c)?\s*\n(.*?)\n```',
            content,
            re.DOTALL
        )
        
        # Extract makefile
        makefile_match = re.search(
            r'===\s*MAKEFILE\s*===\s*```(?:makefile|make)?\s*\n(.*?)\n```',
            content,
            re.DOTALL
        )
        
        if source_match and makefile_match:
            print(f"DEBUG: Successfully parsed source ({len(source_match.group(1))} chars) and makefile ({len(makefile_match.group(1))} chars)")
            return {
                'code': source_match.group(1),
                'makefile': makefile_match.group(1)
            }
        
        # Debug which part failed
        if not source_match:
            print("DEBUG: Failed to match SOURCE block")
        if not makefile_match:
            print("DEBUG: Failed to match MAKEFILE block")
        print(f"DEBUG: Response section around REPAIRED marker: {content[content.find('=== REPAIRED ==='):content.find('=== REPAIRED ===')+500]}")
        
        return None
    
    def submit_variants(variants, classification):
        """
        Submit variants to the evaluation server.
        """

        from config import UNIT_TEST_CODE

        if UNIT_TEST_CODE is None:
            print("ERROR: UNIT_TEST_CODE is None - cannot submit variants")
            return [None] * len(variants)

        candidates = []
        for variant in variants:
            code_content = variant['code']
            makefile_content = variant['makefile']

            # Base64 encode the code and makefile content
            encoded_code = base64.b64encode(code_content.encode('utf-8')).decode('utf-8')
            encoded_makefile = base64.b64encode(makefile_content.encode('utf-8')).decode('utf-8')
            encoded_unittest = base64.b64encode(UNIT_TEST_CODE.encode('utf-8')).decode('utf-8')

            # Prepare the payload
            payload = {
                'code': encoded_code,
                'class': classification,
                'makefile': encoded_makefile,
                'unittest': encoded_unittest
            }
            
            headers = {"Authorization": f"Bearer {SANDBOX_TOKEN}"}

            # Send the POST request to the evaluation server
            try:
                response = requests.post(
                    EVALUATION_SERVER + '/submit',
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                # get candidate_hash from response and retrieve candidate details
                response_data = response.json()
                candidate_hash = response_data.get('candidate_hash')
                candidates.append(candidate_hash)
                        
            except requests.exceptions.RequestException as e:
                print(f"ERROR: Failed to submit variant code to evaluation server: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response status: {e.response.status_code}")
                    print(f"Response body: {e.response.text[:500]}")
                candidates.append(None)
            except Exception as e:
                print(f"ERROR: Unexpected error submitting variant: {type(e).__name__}: {e}")
                candidates.append(None)
        
        return candidates