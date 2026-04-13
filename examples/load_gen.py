import random
import time

import requests
# Spam vLLM with 128K requests to trigger thermal throttle
for i in range(1000):
    prompt = "Write a story. " * 30000  # ~120K tokens
    requests.post("http://localhost:8000/v1/completions", 
                  json={"model": "meta-llama/Meta-Llama-3.1-8B-Instruct", 
                        "prompt": prompt, "max_tokens": 512, "stream": False})
    time.sleep(random.uniform(0.1, 0.5))
