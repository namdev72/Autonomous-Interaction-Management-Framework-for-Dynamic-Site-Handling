# test_agent.py and test_api.py are manual/live scripts (they hit a real
# browser and the real Groq API), not pytest suites -- despite the filename,
# neither is meant to be collected by a bare `pytest` run.
collect_ignore = ["test_agent.py", "test_api.py"]
