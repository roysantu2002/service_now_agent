"""
Log utility module for parsing, structuring, and analyzing logs with LLMs.
"""

import re
import logging
from pathlib import Path
import pandas as pd
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Log Parsing Utilities
# -----------------------------------------------------------------------------
def process_log_file(log_contents: str) -> pd.DataFrame:
    """
    Extract timestamps and structured log entries from raw log text.

    Args:
        log_contents (str): Full contents of the uploaded log file.

    Returns:
        pd.DataFrame: DataFrame with columns ['timestamp', 'log_activity'].
    """
    timestamp_patterns = [
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
        r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",
        r"\w{3} \d{2} \d{2}:\d{2}:\d{2}",
        r"\d{2}:\d{2}:\d{2}",
    ]
    combined_pattern = "|".join(timestamp_patterns)

    timestamps = re.findall(combined_pattern, log_contents)
    log_entries = re.split(combined_pattern, log_contents)[1:]  # ignore empty first

    cleaned_entries = [entry.strip() for entry in log_entries if entry.strip()]

    # Handle mismatch between timestamps and entries
    min_len = min(len(timestamps), len(cleaned_entries))
    timestamps = timestamps[:min_len]
    cleaned_entries = cleaned_entries[:min_len]

    df = pd.DataFrame({"timestamp": timestamps, "log_activity": cleaned_entries})
    return df


# -----------------------------------------------------------------------------
# LLM Query Utility (Azure OpenAI Compatible)
# -----------------------------------------------------------------------------
def query_openai(
    api_key: str,
    question: str,
    df: pd.DataFrame,
    azure_deployment: str,
    azure_endpoint: str,
    api_version: str = "2024-05-01-preview",
) -> str:
    """
    Query Azure OpenAI with structured log data and return intelligent insights.

    Args:
        api_key (str): Azure OpenAI API key.
        question (str): User's question about the logs.
        df (pd.DataFrame): Structured log data.
        azure_deployment (str): Azure OpenAI deployment name.
        azure_endpoint (str): Azure endpoint URL.
        api_version (str, optional): API version to use. Defaults to '2024-05-01-preview'.

    Returns:
        str: LLM-generated insights.
    """
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint,
        )

        # Condense log text (truncate to avoid token overflow)
        logs_text = "\n".join(
            f"[{r.timestamp}] {r.log_activity}" for r in df.itertuples()
        )[:15000]

        system_prompt = (
            "You are a Log Analysis Expert. Analyze the structured log data, "
            "identify anomalies, error patterns, and likely root causes. "
            "Summarize the findings clearly and suggest potential remediations."
        )

        user_prompt = f"Logs:\n{logs_text}\n\nQuestion:\n{question}"

        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()
        return result

    except Exception as e:
        logger.exception("Error while querying OpenAI")
        return f"Error processing OpenAI query: {e}"


# -----------------------------------------------------------------------------
# Optional: Save structured logs locally
# -----------------------------------------------------------------------------
def save_structured_logs(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Save structured log DataFrame as a CSV file for downstream use.

    Args:
        df (pd.DataFrame): Structured log DataFrame.
        output_path (Path): File path to save CSV.

    Returns:
        Path: Saved file path.
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        return output_path
    except Exception as e:
        logger.error(f"Failed to save structured logs: {e}")
        raise
