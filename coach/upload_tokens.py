"""Sube a Supabase los tokens de Garmin generados con login.py (una sola vez).
Variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, COACH_USER_ID"""
import os
from garminconnect import Garmin
from coach.sync import LOCAL_TOKENS, sb

c = Garmin()
c.login(str(LOCAL_TOKENS))
sb().table("garmin_tokens").upsert({"user_id": os.environ["COACH_USER_ID"], "tokens": c.client.dumps()}).execute()
print("tokens subidos")
