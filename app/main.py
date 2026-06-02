"""项目入口 — 启动 Streamlit UI"""

import subprocess
import sys


def main():
    """启动 Streamlit 应用"""
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "app/ui/streamlit_app.py",
        "--server.port", "8501",
    ])


if __name__ == "__main__":
    main()
