# app/services/log_parser.py
import re
import asyncio
from typing import Dict, List, Union
from datetime import datetime
from pathlib import Path
import pandas as pd

from app.abstracts.log_parser import BaseLogParser, ParseResult, LogEntry, LogLevel

# Parser for common web access logs (Apache/Nginx-like).
# It is conservative: treats each input line as a message if it doesn't match,
# and preserves original line in 'message' so downstream code can still use it.
class MultiFileLogParser(BaseLogParser):
    """
    Parse multiple log files asynchronously and produce ParseResult objects.
    Provides:
      - parse_log_file(file_path: str) -> ParseResult
      - parse_multiple_logs(files_or_folder: Union[str, Path, List[str]]) -> Dict[str, ParseResult]
      - logs_to_dataframe(parse_results: Dict[str, ParseResult]) -> pd.DataFrame
    """

    # Regex for common combined log format (IP - - [time] "METHOD url HTTP/1.x" STATUS SIZE "ref" "ua")
    LOG_PATTERN = re.compile(
        r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+-\s+-\s+\[(?P<timestamp>[^\]]+)\]\s+'
        r'"(?P<method>GET|POST|PUT|DELETE|HEAD|OPTIONS|TRACE|CONNECT)\s+(?P<url>[^\s]+)\s+HTTP/[\d.]+"\s+'
        r'(?P<status>\d{3})\s+(?P<size>\d+)(?:\s+"(?P<ref>.*?)"\s+"(?P<ua>.*?)")?'
    )

    # Timestamp pattern for Apache: 22/Jan/2019:03:56:14 +0330
    APACHE_TIME_FMT = "%d/%b/%Y:%H:%M:%S"

    async def parse_log_file(self, file_path: str) -> ParseResult:
        """
        Parse a single file and return a ParseResult.
        Keeps original line in message; if regex matches we extract fields into message too.
        """
        entries: List[LogEntry] = []
        parsing_errors: Dict[str, int] = {}
        patterns_matched: Dict[str, int] = {}

        try:
            # Read lines on thread to avoid blocking event loop
            lines = await asyncio.to_thread(lambda: open(file_path, "r", encoding="utf-8", errors="replace").readlines())
            for raw in lines:
                line = raw.strip()
                if not line:
                    continue

                m = self.LOG_PATTERN.match(line)
                if m:
                    ts_full = m.group("timestamp")
                    # timestamp may include timezone offset; split off offset
                    ts_parts = ts_full.split()
                    ts_part = ts_parts[0] if ts_parts else ts_full
                    try:
                        timestamp = datetime.strptime(ts_part, self.APACHE_TIME_FMT)
                    except Exception:
                        timestamp = datetime.utcnow()

                    # Compose a cleaned message for AI: include ip, method, url, status
                    message = (
                        f"{m.group('ip')} {m.group('method')} {m.group('url')} "
                        f"status={m.group('status')} size={m.group('size')}"
                    )
                    level = LogLevel.INFO
                else:
                    # Line doesn't match — treat whole line as message
                    timestamp = datetime.utcnow()
                    message = line
                    level = LogLevel.INFO
                    parsing_errors[line[:200]] = parsing_errors.get(line[:200], 0) + 1

                entry = LogEntry(
                    timestamp=timestamp,
                    level=level,
                    message=message,
                    source=str(file_path)
                )
                entries.append(entry)

                key = message[:100]
                patterns_matched[key] = patterns_matched.get(key, 0) + 1

        except Exception as e:
            # File read error — return empty parse with error recorded
            parsing_errors[f"__file_read_error__:{file_path}"] = parsing_errors.get(f"__file_read_error__:{file_path}", 0) + 1

        return ParseResult(
            file_name=str(file_path),
            entries=entries,
            total_count=len(entries),
            error_count=0,
            warning_count=0,
            parsing_errors=parsing_errors,
            patterns_matched=patterns_matched
        )

    async def parse_multiple_logs(self, files_or_folder: Union[str, Path, List[str]]) -> Dict[str, ParseResult]:
        """
        Parse multiple logs. Accepts:
          - folder path (str or Path) -> parse all files in it
          - list of file paths -> parse those
        Returns mapping: {file_path: ParseResult}
        """
        files: List[Path] = []
        if isinstance(files_or_folder, (str, Path)):
            folder = Path(files_or_folder)
            if not folder.exists() or not folder.is_dir():
                raise FileNotFoundError(f"Folder not found: {folder}")
            files = [p for p in folder.iterdir() if p.is_file()]
        elif isinstance(files_or_folder, list):
            files = [Path(p) for p in files_or_folder]
        else:
            raise TypeError("files_or_folder must be a folder path or list of file paths")

        # Kick off parse tasks concurrently
        tasks = [self.parse_log_file(str(p)) for p in files]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return {r.file_name: r for r in results}

    def logs_to_dataframe(self, parse_results: Dict[str, ParseResult]) -> pd.DataFrame:
        """
        Convert ParseResult mapping into a pandas DataFrame with columns:
          - timestamp (datetime)
          - source (file path)
          - level (string)
          - message (string)
        The DataFrame is sorted by timestamp, and trimmed to first 100 rows.
        """
        records = []
        for fname, result in parse_results.items():
            for entry in result.entries:
                records.append({
                    "timestamp": entry.timestamp,
                    "source": entry.source,
                    "level": getattr(entry.level, "value", str(entry.level)),
                    "message": entry.message
                })

        if not records:
            return pd.DataFrame(columns=["timestamp", "source", "level", "message"])

        df = pd.DataFrame.from_records(records)
        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df.sort_values("timestamp", inplace=True, na_position="last")
        df.reset_index(drop=True, inplace=True)

        # Keep only first 100 rows for AI analysis
        return df.head(100)
