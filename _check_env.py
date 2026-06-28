from dotenv import load_dotenv
import os
load_dotenv('.env', override=True)
key = os.environ.get('OPENAI_API_KEY', '')
size = os.path.getsize('.env')
print(f'File size: {size} bytes')
if key and key.startswith('sk-'):
    print(f'[OK] OPENAI_API_KEY: {key[:16]}...{key[-4:]}')
    print(f'[OK] LLM_MODEL: {os.environ.get("LLM_MODEL","")}')
    print(f'[OK] ACTIVE_DOMAIN: {os.environ.get("ACTIVE_DOMAIN","")}')
else:
    print('[FAIL] Key not loaded')
