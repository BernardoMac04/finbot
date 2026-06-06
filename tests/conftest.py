import os
import sys

# Adds finbot/ root to path so tests can import data, analysis, ai modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
