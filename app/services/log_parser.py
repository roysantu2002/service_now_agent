# app/services/log_parser.py

import re
import asyncio
from typing import Dict, List
from datetime import datetime
from pathlib import Path
import pandas as pd

from app.abstracts.log_parser import BaseLogParser, ParseResult, LogEntry, LogLevel


class MultiFileLogParser(BaseLogParser):
    """Parse multiple log files asynchronously and clean for AI analysis."""

    # Match Apache/Nginx-like access logs
    LOG_PATTERN = re.compile(
        r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3}) - - '
        r'\[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>GET|POST|PUT|DELETE|HEAD|OPTIONS|TRACE|CONNECT) (?P<url>[^\s]+) HTTP/[\d.]+" '
        r'(?P<status>\d{3}) (?P<size>\d+)(?: ".*?" ".*?")?'
    )

    async def parse_log_file(self, file_path: str | Path) -> ParseResult:
        entries: List[LogEntry] = []
        parsing_errors: Dict[str, int] = {}
        patterns_matched: Dict[str, int] = {}

        try:
            lines = await asyncio.to_thread(lambda: open(file_path, "r", encoding="utf-8").readlines())
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                match = self.LOG_PATTERN.match(line)
                if match:
                    ts_str = match.group("timestamp")
                    try:
                        timestamp = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")
                    except Exception:
                        timestamp = datetime.utcnow()

                    entry = LogEntry(
                        timestamp=timestamp,
                        level=LogLevel.INFO,
                        message=line,
                        source=str(file_path)
                    )
                    entries.append(entry)

                    key = line[:50]
                    patterns_matched[key] = patterns_matched.get(key, 0) + 1
                else:
                    parsing_errors[line] = parsing_errors.get(line, 0) + 1

        except Exception as e:
            parsing_errors[f"__file_read_error__:{file_path}"] = 1

        return ParseResult(
            file_name=str(file_path),
            entries=entries,
            total_count=len(entries),
            error_count=0,
            warning_count=0,
            parsing_errors=parsing_errors,
            patterns_matched=patterns_matched
        )

    async def parse_multiple_logs(self, files_or_folder: str | Path | list[str | Path]) -> Dict[str, ParseResult]:
        """
        Parse multiple log files.

        Can pass:
            - folder path (str or Path) → parses all files in the folder
            - list of file paths → parses only the provided files
        """
        # Normalize input to list of Paths
        if isinstance(files_or_folder, (str, Path)):
            folder = Path(files_or_folder)
            files = [f for f in folder.iterdir() if f.is_file()]
        elif isinstance(files_or_folder, list):
            files = [Path(f) for f in files_or_folder]
        else:
            raise TypeError("Expected a folder path or list of file paths")

        tasks = [self.parse_log_file(f) for f in files]
        results = await asyncio.gather(*tasks)
        return {r.file_name: r for r in results}

    def logs_to_dataframe(self, parse_results: Dict[str, ParseResult]) -> pd.DataFrame:
        """Convert parsed logs to a pandas DataFrame and clean them."""
        records = []
        for fname, result in parse_results.items():
            for entry in result.entries:
                records.append({
                    "timestamp": entry.timestamp,
                    "source": entry.source,
                    "level": entry.level.value,
                    "message": entry.message
                })
        df = pd.DataFrame(records)
        df.sort_values("timestamp", inplace=True)
        return df
