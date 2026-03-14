import sys
import os
from dotenv import load_dotenv
load_dotenv()
from ai_engine import extract_and_parse_with_gemini

class MockFile:
    def __init__(self, name):
        self.filename = name
    def read(self):
        return b"fake-bytes"

API_KEY = os.environ.get("GEMINI_API_KEY", "")
print(extract_and_parse_with_gemini([], API_KEY))
