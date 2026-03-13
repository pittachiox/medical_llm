import sys
from ai_engine import extract_and_parse_with_gemini
class MockFile:
    def __init__(self, name):
        self.filename = name
    def read(self):
        return b"fake-bytes"

print(extract_and_parse_with_gemini([], "AIzaSyDQ1RYF0X9g1PNfCAR1OMv6Ocx-9KL1kOc"))
