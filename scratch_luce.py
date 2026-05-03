import os
import sys

# Add backend app to path
sys.path.append("c:/Users/ashila pe/Desktop/dashboard_bi_ta/dashboard_pelampung/backend")

from app.db.database import SessionLocal
from app.crud.analytics_luce import calculate_luce

db = SessionLocal()
data = calculate_luce(db)
print("LUCE DATA PREVIEW (first 5):")
for d in data[:5]:
    print(d)
