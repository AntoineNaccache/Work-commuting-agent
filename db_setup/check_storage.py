#!/usr/bin/env python3
"""Check how properties are stored in ApertureData"""

import os
from dotenv import load_dotenv
from aperturedb.CommonLibrary import create_connector

load_dotenv()
db_key = os.getenv("APERTUREDB_KEY")
db = create_connector(key=db_key)

# Add a test entity with properties
print("Adding test entity...")
add_query = [
    {
        "AddEntity": {
            "class": "TestEmail",
            "properties": {
                "test_subject": "Test Subject",
                "test_body": "Test Body",
                "test_sender": "test@example.com"
            }
        }
    }
]

response = db.query(add_query)
print("AddEntity response:", response)

# Extract uniqueid if available
uniqueid = None
if isinstance(response, tuple) and len(response) > 0:
    cmd_results = response[0]
    if isinstance(cmd_results, list) and len(cmd_results) > 0:
        result = cmd_results[0]
        if isinstance(result, dict) and "AddEntity" in result:
            add_result = result["AddEntity"]
            uniqueid = add_result.get("uniqueid")
            print(f"Entity uniqueid: {uniqueid}")

# Now try to find it
print("\nFinding test entity...")
find_query = [
    {
        "FindEntity": {
            "with_class": "TestEmail",
            "results": {
                "list": ["properties"]
            },
            "limit": 1
        }
    }
]

response2 = db.query(find_query)
print("FindEntity response:", response2)

# Try finding by uniqueid if we have it
if uniqueid:
    print(f"\nFinding entity by uniqueid {uniqueid}...")
    find_query2 = [
        {
            "FindEntity": {
                "uniqueid": uniqueid,
                "results": {
                    "list": ["properties"]
                }
            }
        }
    ]
    response3 = db.query(find_query2)
    print("FindEntity by uniqueid response:", response3)
