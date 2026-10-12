from pathlib import Path
from config import Settings
from database.repository import Repository
from database.models import Status
from platforms.eligibility import decision
from content.generator import make_draft, validate

def settings(tmp_path): return Settings(database_path=tmp_path/'test.db')
def test_eligibility_filters(tmp_path):
 s=settings(tmp_path)
 assert decision(None,s)[0] == Status.UNVERIFIED
 assert decision({'da':19,'pa':20,'spam_score':1},s)[0] == Status.REJECTED
 assert decision({'da':20,'pa':15,'spam_score':10},s)[0] == Status.REJECTED
 assert decision({'da':20,'pa':15,'spam_score':9.9},s)[0] == Status.ELIGIBLE
def test_draft_contains_required_keyword_and_url(tmp_path):
 s=settings(tmp_path); d=make_draft('Example',s.keyword,s.target_url)
 assert validate(d,s.keyword,s.target_url) == (True,None)
def test_duplicate_platform_and_published_submission_prevention(tmp_path):
 repo=Repository(tmp_path/'test.db'); item={'name':'Example','domain':'example.test','registration_url':'https://x','submission_url':'https://x/s','relevance':'test','terms_url':'https://x/t'}
 first=repo.upsert_platform(item); assert first==repo.upsert_platform(item)
 repo.record_submission(first,None,'https://innovions.org/','PUBLISHED')
 assert repo.submitted(first,'https://innovions.org/')
