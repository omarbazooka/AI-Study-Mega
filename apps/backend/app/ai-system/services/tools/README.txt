Folder: backend/app/ai-system/services/tools/

Description:
This folder defines the custom tools and function-calling implementations
available to AI agents. Tools extend agent capabilities beyond simple
text generation by enabling real-world actions and data retrieval.

Responsibilities:
- Implement tool functions callable via LLM function-calling or tool-use APIs
- Define tool schemas (name, description, parameters) for LLM registration
- Wrap external APIs, calculators, search engines, and code interpreters
- Handle tool execution errors and format results for agent consumption

Integration:
Tools are registered with agents in ai-system/agents/ and invoked during
agent reasoning loops. They may call external APIs, query app/db/, or trigger
background tasks in app/workers/. Results are fed back into the agent context
for continued reasoning.
