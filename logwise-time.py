#!/usr/bin/env python3
"""
LogWise - AI-Powered Log Analysis & RCA Assistant
Now supports syslog-style and dmesg-style timestamps with --time, --before, --after
"""

import argparse
import json
import sys
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import re


def check_connection(ollama_url: str) -> bool:
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def ensure_model(ollama_url: str, model: str) -> bool:
    try:
        response = requests.get(f"{ollama_url}/api/tags")
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                if m.get('name') == model:
                    return True

        print(f"Model {model} not found. Attempting to pull...")
        result = subprocess.run(['ollama', 'pull', model],
                                capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking model availability: {e}")
        return False


def parse_log_time(line: str) -> Optional[datetime]:
    """
    Parse both syslog and dmesg style timestamps:
    - syslog: 'Sep  9 13:12:42'
    - dmesg:  '[Tue Sep  9 13:12:42 2025]'
    """
    # dmesg style
    dmesg_match = re.match(r'^\[(\w{3}) (\w{3})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2}) (\d{4})\]', line)
    if dmesg_match:
        _, month, day, time_str, year = dmesg_match.groups()
        try:
            ts_str = f"{month} {day} {year} {time_str}"
            return datetime.strptime(ts_str, "%b %d %Y %H:%M:%S")
        except ValueError:
            return None

    # syslog style
    syslog_match = re.match(r'^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})', line)
    if syslog_match:
        month, day, time_str = syslog_match.groups()
        year = datetime.now().year
        try:
            ts_str = f"{month} {day} {year} {time_str}"
            return datetime.strptime(ts_str, "%b %d %Y %H:%M:%S")
        except ValueError:
            return None

    return None


def filter_logs_by_time(lines: List[str], target_time: str,
                        before: str, after: str) -> List[str]:
    """
    Filter logs around given timestamp with before/after window.
    target_time format: Sep-09T13:10
    """
    try:
        target_dt = datetime.strptime(target_time, "%b-%dT%H:%M")
        target_dt = target_dt.replace(year=datetime.now().year)
    except ValueError:
        print("Error: --time format must be like 'Sep-09T13:10'", file=sys.stderr)
        return []

    def parse_offset(s: str) -> timedelta:
        if s.endswith("m"):
            return timedelta(minutes=int(s[:-1]))
        elif s.endswith("h"):
            return timedelta(hours=int(s[:-1]))
        elif s.endswith("s"):
            return timedelta(seconds=int(s[:-1]))
        else:
            return timedelta(minutes=int(s))

    before_td = parse_offset(before)
    after_td = parse_offset(after)

    start_window = target_dt - before_td
    end_window = target_dt + after_td

    filtered = []
    for line in lines:
        ts = parse_log_time(line)
        if ts and start_window <= ts <= end_window:
            filtered.append(line)

    return filtered


def preprocess(content: str) -> str:
    lines = content.strip().split('\n')
    filtered_lines = [line.strip() for line in lines if line.strip() and len(line) < 1000]
    if len(filtered_lines) > 200:
        filtered_lines = filtered_lines[:100] + ["... (truncated) ..."] + filtered_lines[-100:]
    return '\n'.join(filtered_lines)


def analyze_logs(log_content: str, ollama_url: str, model: str) -> Dict:
    if not check_connection(ollama_url):
        return {"error": "Cannot connect to Ollama. Ensure it is running."}

    if not ensure_model(ollama_url, model):
        return {"error": f"Model {model} is not available."}

    preprocessed = preprocess(log_content)

    prompt = f"""
You are an expert in troubleshooting and root cause analysis across IT systems.
Analyze the following log entries and provide a clear, human-readable report.

## SUMMARY
## ISSUES IDENTIFIED
## SEVERITY ASSESSMENT
## ROOT CAUSE HYPOTHESIS
## RECOMMENDATIONS
## PATTERNS OBSERVED

Logs:
{preprocessed}
"""

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300
        )
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "analysis": result.get("response", "No response generated"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"error": f"API request failed with status {response.status_code}"}
    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def format_output(analysis_result: Dict, format_type: str, model: str) -> str:
    if "error" in analysis_result:
        return f"Error: {analysis_result['error']}"

    if format_type == "json":
        return json.dumps(analysis_result, indent=2)

    output = []
    output.append("LogWise - AI LOG ANALYSIS & RCA REPORT")
    output.append("=" * 60)
    output.append(f"Generated: {analysis_result.get('timestamp', 'Unknown')}")
    output.append("")
    output.append(analysis_result.get('analysis', 'No analysis available'))
    output.append("")
    output.append("=" * 60)
    output.append(f"Generated by LogWise (Model: {model})")
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="LogWise - AI-powered log analysis and troubleshooting assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  logwise -f /var/log/syslog --time Sep-09T13:10 --before 10m --after 1h
  logwise -f /home/vinil/dmesg.log --time Sep-09T13:12 --before 2m --after 2m
        """
    )

    parser.add_argument('-f', '--file', help='Log file to analyze')
    parser.add_argument('--stdin', action='store_true', help='Read log content from stdin')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--lines', type=int, default=0, help='Number of lines from end of file (0 = all)')
    parser.add_argument('--url', default='http://localhost:11434', help='Ollama API URL')
    parser.add_argument('--model', default='llama3:8b', help='Model to use for analysis')
    parser.add_argument('--time', help="Target timestamp (e.g., 'Sep-09T13:10')")
    parser.add_argument('--before', default="5m", help="Time window before target (e.g., 10m, 1h)")
    parser.add_argument('--after', default="5m", help="Time window after target (e.g., 2m, 30s)")

    args = parser.parse_args()

    if not args.file and not args.stdin:
        parser.error("Must specify either --file or --stdin")
    if args.file and args.stdin:
        parser.error("Cannot specify both --file and --stdin")

    try:
        if args.stdin:
            lines = sys.stdin.read().splitlines()
        else:
            if not os.path.exists(args.file):
                print(f"Error: File '{args.file}' not found", file=sys.stderr)
                sys.exit(1)

            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
    except Exception as e:
        print(f"Error reading log content: {e}", file=sys.stderr)
        sys.exit(1)

    if args.lines > 0:
        lines = lines[-args.lines:]

    if args.time:
        lines = filter_logs_by_time(lines, args.time, args.before, args.after)

    if not lines:
        print("Error: No log content to analyze (check --time format or window size)", file=sys.stderr)
        sys.exit(1)

    log_content = ''.join(lines)

    print("Analyzing logs with AI...", file=sys.stderr)
    result = analyze_logs(log_content, args.url, args.model)
    formatted_output = format_output(result, args.format, args.model)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            print(f"Analysis saved to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(formatted_output)


if __name__ == "__main__":
    main()
