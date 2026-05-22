from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017")
db = client["pharma_adk"]
for b in db.briefings.find():
    print("Briefing:", b.get("_id"), b.get("meeting_id"), b.get("source"), b.get("generated_by"))
