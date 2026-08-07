import sys
import os

# Loyiha ildizini qo'shish
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel uchun
app = app