import os, sys
from pathlib import Path
# Ensure backend is importable for engine/models/seed/auth imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
load_dotenv(Path(__file__).resolve().parents[2] / 'frontend' / '.env')
