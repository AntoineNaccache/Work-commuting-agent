#!/usr/bin/env python3
"""Verify that emails are stored in ApertureData"""

import os
from dotenv import load_dotenv
from aperturedb.CommonLibrary import create_connector

load_dotenv()
db_key = os.getenv("APERTUREDB_KEY")

if not db_key:
    print("⚠️  No APERTUREDB_KEY found in environment")
    exit(1)

try:
    db = create_connector(key=db_key)
    print("✅ Connected to ApertureData")
    
    # Query all Email entities with specific property names in the list
    print("Querying Email entities...")
    query = [
        {
            "FindEntity": {
                "with_class": "Email",
                "results": {
                    "list": ["subject", "sender", "body", "is_spam", "is_unread", "timestamp", "entity_id"]
                }
            }
        }
    ]
    
    response = db.query(query)
    
    # Parse response - format: ([{'FindEntity': {'entities': [...], 'returned': 30}}], [])
    emails = []
    if isinstance(response, tuple) and len(response) > 0:
        command_results = response[0]
        if isinstance(command_results, list) and len(command_results) > 0:
            result = command_results[0]
            if isinstance(result, dict) and "FindEntity" in result:
                find_result = result["FindEntity"]
                # Entities are in "entities" field
                if "entities" in find_result:
                    entities_list = find_result["entities"]
                    # Reconstruct properties from individual fields
                    for e in entities_list:
                        if isinstance(e, dict):
                            # Properties are returned at top level when querying specific fields
                            props = {k: v for k, v in e.items() if k not in ["_uniqueid", "_class"]}
                            e["properties"] = props
                    emails = entities_list
                elif "returned" in find_result:
                    returned = find_result["returned"]
                    if isinstance(returned, list):
                        emails = returned
    
    count = len(emails) if isinstance(emails, list) else 0
    print(f"✅ Found {count} email entities in the database")
    
    if count > 0:
        print("\nSample emails:")
        for i, email in enumerate(emails[:10], 1):
            # Properties might be nested in "properties" or at top level
            if isinstance(email, dict):
                props = email.get("properties", {})
                # If properties is None or empty, check if properties are at top level
                if not props or props is None:
                    # Properties might be stored directly in the email dict
                    props = {k: v for k, v in email.items() if k not in ["_uniqueid", "_class", "properties"]}
            else:
                props = {}
            
            # Extract property values
            subject = str(props.get("subject", "N/A"))[:60] if props else "N/A"
            spam = props.get("is_spam", False) if props else False
            unread = props.get("is_unread", False) if props else False
            sender = str(props.get("sender", "N/A"))[:40] if props else "N/A"
            
            print(f"\n  {i}. Subject: {subject}")
            print(f"     From: {sender}")
            print(f"     Spam: {spam}, Unread: {unread}")
            
            # Debug: show first email structure
            if i == 1:
                print(f"     [DEBUG] Email keys: {list(email.keys())}")
                print(f"     [DEBUG] Properties type: {type(props)}, keys: {list(props.keys())[:5] if props else 'N/A'}")
        
        # Count spam vs regular
        spam_count = 0
        unread_count = 0
        for e in emails:
            if isinstance(e, dict):
                props = e.get("properties", {})
                if props and isinstance(props, dict):
                    if props.get("is_spam", False):
                        spam_count += 1
                    if props.get("is_unread", False):
                        unread_count += 1
        
        print(f"\n📊 Statistics:")
        print(f"   Total emails: {count}")
        print(f"   Spam emails: {spam_count}")
        print(f"   Unread emails: {unread_count}")
        
        if props == {}:
            print("\n⚠️  Note: Properties are showing as empty/None.")
            print("   This may indicate a query format issue. Entities are stored but properties need different retrieval method.")
    else:
        print("⚠️  No emails found in database")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
