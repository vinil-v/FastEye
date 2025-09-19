#!/usr/bin/env python3
"""
FastEye - Accelerate incident resolution with AI-powered log analysis,
Dropdown for exact event time, Duration, hidden Ollama config, and download RCA report as text file.
Author - Vinil Vadakkepurakkal
Date - 18/9/25
"""

import streamlit as st
import requests
import re
from datetime import datetime, timedelta

def parse_bracketed_syslog_datetime(line):
    pattern = r'\[(\w{3})\s+(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+(\d{4})\]'
    match = re.match(pattern, line)
    if not match:
        return None
    _, month_str, day, hour, minute, second, year = match.groups()
    try:
        month = datetime.strptime(month_str, '%b').month
        return datetime(int(year), month, int(day), int(hour), int(minute), int(second))
    except Exception:
        return None

def parse_traditional_syslog_datetime(line, year):
    pattern = r'([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})'
    match = re.match(pattern, line)
    if not match:
        return None
    month_str, day, hour, minute, second = match.groups()
    try:
        month = datetime.strptime(month_str, '%b').month
        return datetime(year, month, int(day), int(hour), int(minute), int(second))
    except Exception:
        return None

def detect_timestamp_format(log_content):
    for line in log_content.splitlines():
        if parse_bracketed_syslog_datetime(line):
            return "bracketed"
    return "traditional"

def detect_year_and_times(log_content, timestamp_format):
    if timestamp_format == "bracketed":
        times = [parse_bracketed_syslog_datetime(line) for line in log_content.splitlines()]
        times = [dt for dt in times if dt is not None]
        unique_times = sorted(set(times))
        year = unique_times[0].year if unique_times else datetime.now().year
        return year, unique_times
    else:
        year_match = re.search(r'(\d{4})[-/]', log_content)
        year = int(year_match.group(1)) if year_match else datetime.now().year
        times = [parse_traditional_syslog_datetime(line, year) for line in log_content.splitlines()]
        times = [dt for dt in times if dt is not None]
        unique_times = sorted(set(times))
        return year, unique_times

def filter_syslog_by_time(log_content, start, duration_minutes, year, timestamp_format):
    end = start + timedelta(minutes=duration_minutes)
    filtered = []
    for line in log_content.splitlines():
        if timestamp_format == "bracketed":
            dt = parse_bracketed_syslog_datetime(line)
        else:
            dt = parse_traditional_syslog_datetime(line, year)
        if dt and start <= dt < end:
            filtered.append(line)
    return '\n'.join(filtered)

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
#    st.title("LogWise")
#    st.write("Accelerate incident resolution with AI-powered log analysis")
    st.set_page_config(page_title="FastEye")
    st.markdown(
    """
    <div style="text-align: center;">
        <h1 style="margin-bottom: 0;">FastEye</h1>
        <p style="font-size:18px; font-style: italic; margin-top: 0; color: #555;">
            Accelerate incident resolution with AI-powered log analysis
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

    st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: transparent;
        color: gray;
        text-align: center;
        font-size: 14px;
        padding: 10px 0;
        user-select: none;
    }
    </style>

    <div class="footer">
        FastEye MVP Project – Hackathon 2025 By Vinil, Jiyesh, and Christian
    </div>
    """,
    unsafe_allow_html=True,
)

    ollama_url = st.secrets["ollama"]["url"]
    model = st.secrets["ollama"]["model"]

    uploaded_file = st.file_uploader("Upload a log file", type=["log", "txt"])

    if uploaded_file:
        raw_content = uploaded_file.read().decode("utf-8", errors='ignore')

        timestamp_format = detect_timestamp_format(raw_content)
        st.markdown(f"**Detected timestamp format:** `{timestamp_format}`")

        detected_year, detected_times = detect_year_and_times(raw_content, timestamp_format)
        if not detected_times:
            st.warning("No valid timestamped lines detected.")
            return

        st.markdown(f"**Detected year:** {detected_year}")
        st.markdown("**Select exact event time:**")

        time_options = [dt.strftime('%Y-%m-%d %H:%M:%S') for dt in detected_times]
        selected_time_str = st.selectbox("Event Time:", time_options)
        selected_datetime = datetime.strptime(selected_time_str, '%Y-%m-%d %H:%M:%S')

        duration_minutes = st.number_input("Duration (minutes):", min_value=1, max_value=1440, value=5)

        analysis_result = None

        if st.button("Run AI RCA Analysis"):
            st.info("Filtering logs and running analysis...")
            filtered_logs = filter_syslog_by_time(raw_content, selected_datetime, duration_minutes, detected_year, timestamp_format)
            if not filtered_logs.strip():
                st.warning("No logs found in the selected time window.")
            else:
                result = analyze_logs(filtered_logs, ollama_url, model)
                if "error" in result:
                    st.error(result["error"])
                else:
                    analysis_result = result['analysis']
                    st.success(f"Analysis completed at {result['timestamp']}")

        if analysis_result:
            st.text_area("RCA Report", value=analysis_result, height=400)

            st.download_button(
                label="Download RCA Report as Text File",
                data=analysis_result,
                file_name="rca_report.txt",
                mime="text/plain"
            )

            st.info("Disclaimer: This response is generated by FastEye, an open-source AI model. While it provides helpful guidance, please verify the information independently. AI-generated outputs may occasionally be incomplete or inaccurate.")

if __name__ == "__main__":
    main()