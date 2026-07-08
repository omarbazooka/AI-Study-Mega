import csv
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Typical costs per 1 million tokens (for tracking/cost control)
MODEL_PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "default": {"input": 0.10, "output": 0.15}
}

class TokenTracker:
    """Logs token usage, API latency, and costs to console and local file storage."""
    def __init__(self, log_dir: str = "logs", filename: str = "llm_usage.csv"):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, filename)
        self._lock = threading.Lock()
        self._initialize_log_file()

    def _initialize_log_file(self):
        """Creates the log directory and CSV file with headers if they do not exist."""
        with self._lock:
            os.makedirs(self.log_dir, exist_ok=True)
            if not os.path.exists(self.log_file):
                with open(self.log_file, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp",
                        "user_id",
                        "document_id",
                        "task_type",
                        "provider",
                        "model",
                        "key_alias",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "latency_ms",
                        "status",
                        "error_type",
                        "prompt_version",
                        "estimated_cost_usd"
                    ])

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates estimated request cost based on token counts and model pricing."""
        rates = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        return round(input_cost + output_cost, 6)

    def log_usage(
        self,
        user_id: str,
        document_id: str,
        task_type: str,
        provider: str,
        model: str,
        key_alias: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        status: str,
        error_type: Optional[str] = None,
        prompt_version: str = "v1"
    ):
        """Appends a usage log record thread-safely."""
        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Console logging (never exposing actual keys, using alias)
        logger.info(
            f"[LLM LOG] user={user_id} doc={document_id} task={task_type} "
            f"model={model} alias={key_alias} tokens={total_tokens} "
            f"latency={latency_ms}ms status={status} cost=${cost:.6f}"
        )

        with self._lock:
            try:
                with open(self.log_file, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp,
                        user_id,
                        document_id,
                        task_type,
                        provider,
                        model,
                        key_alias,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        latency_ms,
                        status,
                        error_type or "",
                        prompt_version,
                        f"{cost:.6f}"
                    ])
            except Exception as e:
                logger.error(f"Failed to write token usage log to CSV: {e}")


# Global token tracker instance
token_tracker = TokenTracker()
