import subprocess
import sys


def test_help_runs():
    result = subprocess.run([sys.executable, "-m", "cli.main", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Made-in-China.com Scraper" in result.stdout

