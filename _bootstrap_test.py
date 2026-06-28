from dotenv import load_dotenv
load_dotenv('.env', override=True)
import os
os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))

key = os.environ.get('OPENAI_API_KEY', '')
if not key:
    raise SystemExit('[FAIL] OPENAI_API_KEY not set')
print(f'[OK] Key: {key[:16]}...{key[-4:]}')

from config.settings import initialize
from utils import setup_logging
from data import bootstrap_data_layer
from memory import get_memory_store
from knowledge import bootstrap_knowledge_layer
from connectors import get_connector
from agents.tool_implementations import register_all_tools
from registry import register_domain_tools, register_domain_agents
from workflow.executor import WorkflowExecutor

cfg = initialize('config/platform.yaml', 'config/domains', None)
setup_logging(cfg.logging)
domain = cfg.current_domain

bootstrap_data_layer(cfg, seed=True, force_reseed=False)
store = get_memory_store(cfg.vector_db, cfg.embedding)
retrieval_svc = bootstrap_knowledge_layer(cfg, store, force_reingest=False)
connector = get_connector(domain.name)
register_all_tools(connector, retrieval_svc)
tools = register_domain_tools(domain)
register_domain_agents(domain, cfg.llm, tools)
executor = WorkflowExecutor(domain, cfg, retrieval_svc)

print('[OK] Full platform bootstrap SUCCESS')
print(f'[OK] Domain: {domain.name}')
print(f'[OK] LLM model: {cfg.llm.model}')
