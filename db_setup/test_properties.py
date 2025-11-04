#!/usr/bin/env python3
"""Test property retrieval from ApertureData"""

import os
import sys
from dotenv import load_dotenv
from aperturedb.CommonLibrary import create_connector

load_dotenv()
db_key = os.getenv("APERTUREDB_KEY")

if not db_key:
    print("No key found")
    sys.exit(1)

db = create_connector(key=db_key)

# Try querying without list parameter first
print("Test 1: FindEntity without list parameter")
query1 = [
    {
        "FindEntity": {
            "with_class": "Email",
            "limit": 1
        }
    }
]
response1 = db.query(query1)
print("Response:", response1)

# Try querying ALL entities and see full response structure
print("\nTest 2: FindEntity with all entities, full structure")
query2 = [
    {
        "FindEntity": {
            "with_class": "Email",
            "results": {
                "list": ["properties"]
            },
            "limit": 3
        }
    }
]
response2 = db.query(query2)
print("Response type:", type(response2))
if isinstance(response2, tuple):
    print("Response[0] type:", type(response2[0]))
    if isinstance(response2[0], dict):
        print("Response[0] keys:", response2[0].keys())
    elif isinstance(response2[0], list):
        print("Response[0] length:", len(response2[0]))
        if response2[0]:
            print("Response[0][0]:", response2[0][0])
            if isinstance(response2[0][0], dict):
                print("Response[0][0] keys:", response2[0][0].keys())
                if "FindEntity" in response2[0][0]:
                    fe = response2[0][0]["FindEntity"]
                    print("FindEntity keys:", fe.keys())
                    if "entities" in fe:
                        entities = fe["entities"]
                        print(f"Found {len(entities)} entities")
                        if entities:
                            print("First entity:", entities[0])
                            print("First entity type:", type(entities[0]))
                            if isinstance(entities[0], dict):
                                print("First entity keys:", entities[0].keys())

# Try getting entity by uniqueid and see full structure
print("\nTest 3: GetEntity by uniqueid")
query3 = [
    {
        "GetEntity": {
            "uniqueid": 1
        }
    }
]
response3 = db.query(query3)
print("Response:", response3)
