#!/usr/bin/env python3
"""
LogWise - Linux Syslog RCA Web Tool with Auto Date/Time Detection,
Dropdown for exact event time, Duration, and hidden Ollama config.
"""

import streamlit as st
import requests
import re
from datetime import datetime, timedelta

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
        return False
    except Exception:
        return False

def parse_syslog_datetime(line, year):
    match = re.match(r'([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})', line)
    if not match:
        return None
    try:
        month_str, day, hour, minute, second = match.groups()
        month = datetime.strptime(month_str, '%b').month
        return datetime(year, month, int(day), int(hour), int(minute), int(second))
    except Exception:
        return None

def detect_year_and_times(log_content):
    year_match = re.search(r'(\d{4})[-/]', log_content)
    if year_match:
        year = int(year_match.group(1))
    else:
        year = datetime.now().year

    datetimes = []
    for line in log_content.splitlines():
        dt = parse_syslog_datetime(line, year)
        if dt:
            datetimes.append(dt)
    unique_times = sorted(list(set(datetimes)))
    return year, unique_times

def filter_syslog_by_time(log_content, start, duration_minutes, year):
    end = start + timedelta(minutes=duration_minutes)
    filtered = []
    for line in log_content.splitlines():
        dt = parse_syslog_datetime(line, year)
        if dt and start <= dt < end:
            filtered.append(line)
    return '\n'.join(filtered)

def analyze_logs(log_content, ollama_url, model):
    if not check_connection(ollama_url):
        return {"error": "Cannot connect to Ollama. Ensure it is running."}
    if not ensure_model(ollama_url, model):
        return {"error": f"Model {model} not available."}
    prompt = f"""
You are an expert in troubleshooting and root cause analysis for IT systems and infrastructure.
Analyze the following Linux syslog entries and provide a detailed RCA report.

{log_content}
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

def main():
    st.title("LogWise - Linux Syslog RCA Tool")
    st.write("Upload a Linux syslog file to auto-detect timestamps, select event, duration, and analyze.")

    # Ollama URL and model from Streamlit secrets, not displayed in UI
    ollama_url = st.secrets["ollama"]["url"]
    model = st.secrets["ollama"]["model"]

    uploaded_file = st.file_uploader("Upload syslog log file", type=["log", "txt"])

    if uploaded_file:
        raw_content = uploaded_file.read().decode("utf-8", errors='ignore')

        detected_year, detected_times = detect_year_and_times(raw_content)
        if not detected_times:
            st.warning("No valid timestamped lines detected in syslog.")
            return

        st.markdown(f"**Detected year:** {detected_year}")
        st.markdown("**Detected event times (sorted):**")

        time_options = [dt.strftime('%Y-%m-%d %H:%M:%S') for dt in detected_times]
        selected_time_str = st.selectbox("Select exact event time:", time_options)
        selected_datetime = datetime.strptime(selected_time_str, '%Y-%m-%d %H:%M:%S')

        duration_minutes = st.number_input("Duration in minutes:", min_value=1, max_value=1440, value=30)

        if st.button("Run AI RCA Analysis"):
            st.info("Filtering logs and running analysis, please wait...")
            filtered_logs = filter_syslog_by_time(raw_content, selected_datetime, duration_minutes, detected_year)
            if not filtered_logs.strip():
                st.warning("No logs found in the selected time window.")
            else:
                result = analyze_logs(filtered_logs, ollama_url, model)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"Analysis completed at {result['timestamp']}")
                    st.text_area("RCA report", value=result['analysis'], height=400)

if __name__ == "__main__":
    main()