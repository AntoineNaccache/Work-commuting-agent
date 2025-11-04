#!/usr/bin/env python3
"""
Setup script for ApertureData multimodal email database.
Generates sample emails with images and attachments and stores them in ApertureData.
"""

import os
import json
import base64
from datetime import datetime, timedelta
from faker import Faker
from PIL import Image
import io
import random
from typing import Dict, List, Any

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Import ApertureData SDK
create_connector = None
Connector = None
Entities = None
Images = None
Query = None
try:
    from aperturedb.CommonLibrary import create_connector
    from aperturedb import Connector
    from aperturedb.Entities import Entities
    from aperturedb.Images import Images
    from aperturedb import Query
except ImportError:
    print("Warning: aperturedb package not found.")
    print("The script will generate sample emails and save to JSON only.")
    print("Install with: pip install -r requirements.txt")

fake = Faker()
Faker.seed(42)


def create_sample_image(width=800, height=600, format='PNG') -> bytes:
    """Create a sample image for email attachments."""
    img = Image.new('RGB', (width, height), color=(random.randint(0, 255), 
                                                    random.randint(0, 255), 
                                                    random.randint(0, 255)))
    # Add some text or pattern
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except:
        font = ImageFont.load_default()
    draw.text((width//4, height//2), "Sample Email Attachment", 
              fill=(255, 255, 255), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


def create_sample_pdf_content() -> bytes:
    """Create a sample PDF content (simplified version)."""
    pdf_content = """%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Sample PDF Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000278 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
385
%%EOF"""
    return pdf_content.encode('utf-8')


def generate_sample_email(is_spam=False, is_unread=True, has_image=False, has_attachment=False) -> Dict[str, Any]:
    """Generate a sample email with optional images and attachments."""
    
    # Generate email metadata
    sender = fake.email()
    recipient = fake.email()
    subject = fake.sentence(nb_words=6)
    
    if is_spam:
        spam_subjects = [
            "URGENT: You've Won $1,000,000!",
            "Limited Time Offer - Act Now!",
            "Congratulations! Claim Your Prize",
            "Get Rich Quick - No Investment Required",
            "Free iPhone - Click Here Now!"
        ]
        subject = random.choice(spam_subjects)
        sender = fake.email(domain="spam-suspicious-site.com")
    
    # Generate email body
    body = fake.text(max_nb_chars=500)
    
    # Add some structure
    email_body = f"""
{body}

Best regards,
{fake.name()}
"""
    
    # Generate timestamp (within last 30 days)
    days_ago = random.randint(0, 30)
    timestamp = datetime.now() - timedelta(days=days_ago)
    
    # Create email document
    email_doc = {
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "body": email_body.strip(),
        "timestamp": timestamp.isoformat(),
        "is_spam": is_spam,
        "is_unread": is_unread,
        "has_image": has_image,
        "has_attachment": has_attachment,
    }
    
    # Add image if requested
    if has_image:
        image_data = create_sample_image()
        email_doc["image_data"] = base64.b64encode(image_data).decode('utf-8')
        email_doc["image_format"] = "PNG"
    
    # Add attachments if requested
    if has_attachment:
        attachments = []
        
        # Add PDF attachment
        pdf_data = create_sample_pdf_content()
        attachments.append({
            "filename": f"document_{random.randint(1000, 9999)}.pdf",
            "content_type": "application/pdf",
            "data": base64.b64encode(pdf_data).decode('utf-8'),
            "size": len(pdf_data)
        })
        
        # Add image attachment
        img_attachment = create_sample_image(400, 300)
        attachments.append({
            "filename": f"image_{random.randint(1000, 9999)}.png",
            "content_type": "image/png",
            "data": base64.b64encode(img_attachment).decode('utf-8'),
            "size": len(img_attachment)
        })
        
        email_doc["attachments"] = attachments
    
    return email_doc


def setup_aperturedb():
    """Setup ApertureData with sample emails."""
    
    # Check if SDK is available
    if create_connector is None and Connector is None:
        print("\n⚠️  ApertureData SDK not available.")
        print("Generating and saving sample emails to JSON file...")
        save_emails_to_json()
        return
    
    # Parse connection details from environment
    # Priority: key > URL > host/port with credentials
    db_key = os.getenv("APERTUREDB_KEY", "")
    db_url = os.getenv("APERTUREDB_URL", "")
    db_host = os.getenv("APERTUREDB_HOST", "localhost")
    db_port = int(os.getenv("APERTUREDB_PORT", "55555"))
    username = os.getenv("APERTUREDB_USERNAME", "")
    password = os.getenv("APERTUREDB_PASSWORD", "")
    token = os.getenv("APERTUREDB_TOKEN", "")
    use_ssl = os.getenv("APERTUREDB_USE_SSL", "true").lower() == "true"
    
    db = None
    
    try:
        # Method 1: Use create_connector with key (recommended for cloud instances)
        if db_key and create_connector:
            print(f"Connecting to ApertureData using key...")
            db = create_connector(key=db_key)
            print("Connected to ApertureData successfully!")
        
        # Method 2: Parse URL and use create_connector or direct Connector
        elif db_url and not db:
            # Parse URL (e.g., "https://host:port" or "hostname")
            if "://" in db_url:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                db_host = parsed.hostname or db_url.split("://")[1].split(":")[0]
                db_port = parsed.port or (443 if parsed.scheme == "https" else 55555)
                use_ssl = parsed.scheme == "https" or use_ssl
            else:
                # Just hostname (cloud URL)
                db_host = db_url
                if "cloud.aperturedata.io" in db_host or "aperturedata.io" in db_host:
                    use_ssl = True
                    db_port = 443 if db_port == 55555 else db_port
            
            print(f"Connecting to ApertureData at {db_host}:{db_port} (SSL: {use_ssl})...")
            
            # Try with credentials if provided
            if token and Connector:
                db = Connector(host=db_host, port=db_port, token=token, use_ssl=use_ssl)
            elif username and password and Connector:
                db = Connector(host=db_host, port=db_port, user=username, password=password, use_ssl=use_ssl)
            elif Connector:
                db = Connector(host=db_host, port=db_port, use_ssl=use_ssl)
            
            print("Connected to ApertureData successfully!")
        
        # Method 3: Use direct host/port
        elif not db and Connector:
            print(f"Connecting to ApertureData at {db_host}:{db_port} (SSL: {use_ssl})...")
            if token:
                db = Connector(host=db_host, port=db_port, token=token, use_ssl=use_ssl)
            elif username and password:
                db = Connector(host=db_host, port=db_port, user=username, password=password, use_ssl=use_ssl)
            else:
                db = Connector(host=db_host, port=db_port, use_ssl=use_ssl)
            print("Connected to ApertureData successfully!")
        
        if db is None:
            raise Exception("Could not initialize ApertureData connection. Check your configuration.")
        
    except Exception as e:
        print(f"\n⚠️  Could not connect to ApertureData: {e}")
        print("This might be because:")
        print("  1. ApertureData server is not running")
        print("  2. Connection host/port/credentials are incorrect")
        print("  3. Network/firewall issues")
        print("\nSaving sample emails to JSON file instead...")
        save_emails_to_json()
        return
    
    # Generate sample emails
    print("\nGenerating sample emails...")
    emails = []
    
    # Generate 10 regular emails
    for i in range(7):
        email = generate_sample_email(
            is_spam=False,
            is_unread=random.choice([True, False]),
            has_image=random.choice([True, False]),
            has_attachment=random.choice([True, False])
        )
        emails.append(email)
    
    # Generate 3 spam emails
    for i in range(3):
        email = generate_sample_email(
            is_spam=True,
            is_unread=True,
            has_image=False,
            has_attachment=False
        )
        emails.append(email)
    
    print(f"Generated {len(emails)} sample emails")
    
    # Store emails in ApertureData
    print("\nStoring emails in ApertureData...")
    stored_count = 0
    
    try:
        for idx, email in enumerate(emails, 1):
            try:
                # Prepare entity properties (metadata)
                entity_properties = {
                    "sender": email["sender"],
                    "recipient": email["recipient"],
                    "subject": email["subject"],
                    "body": email["body"],
                    "timestamp": email["timestamp"],
                    "is_spam": email["is_spam"],
                    "is_unread": email["is_unread"],
                    "email_text": f"{email['subject']} {email['body']}",  # For text search
                }
                
                # Create entity name/ID
                entity_id = f"email_{idx}_{email['subject'][:30].replace(' ', '_').replace('/', '_')}"
                
                # Store as Entity using AddEntity command
                # Build query to add entity
                # Add the entity_id as a property for easy reference
                entity_properties["entity_id"] = entity_id
                entity_properties["email_id"] = entity_id
                
                add_entity_query = [
                    {
                        "AddEntity": {
                            "class": "Email",
                            "properties": entity_properties
                        }
                    }
                ]
                
                # Execute query
                response = db.query(add_entity_query)
                
                # Check if the query was successful
                # Response format: ([{'AddEntity': {'status': 0}}], [])
                if not response:
                    raise Exception(f"No response from AddEntity query")
                
                # Handle tuple response format
                entity_uniqueid = None
                if isinstance(response, tuple) and len(response) > 0:
                    command_results = response[0]  # First element contains command results
                    if isinstance(command_results, list) and len(command_results) > 0:
                        result = command_results[0]
                        if isinstance(result, dict) and "AddEntity" in result:
                            add_result = result["AddEntity"]
                            status = add_result.get("status", -1)
                            if status != 0:
                                error_info = add_result.get("info", "Unknown error")
                                raise Exception(f"AddEntity failed: {error_info}")
                            # Get the uniqueid if returned
                            entity_uniqueid = add_result.get("uniqueid") or add_result.get("entity_id")
                        # Success - status is 0
                    else:
                        raise Exception(f"Unexpected response format: {response}")
                elif isinstance(response, list) and len(response) > 0:
                    # Handle list format directly
                    result = response[0]
                    if isinstance(result, dict):
                        status = result.get("status", -1)
                        if status != 0:
                            error_info = result.get("info", "Unknown error")
                            raise Exception(f"AddEntity failed: {error_info}")
                else:
                    raise Exception(f"Unexpected response format: {response}")
                
                # If email has embedded image, store it separately
                if email.get("image_data"):
                    try:
                        image_bytes = base64.b64decode(email["image_data"])
                        image_id = f"{entity_id}_image"
                        
                        # Store image using AddImage command
                        add_image_query = [
                            {
                                "AddImage": {
                                    "_blob": image_bytes,
                                    "properties": {
                                        "email_id": entity_id,
                                        "format": email.get("image_format", "PNG")
                                    }
                                }
                            }
                        ]
                        
                        # Link image to email entity
                        link_query = [
                            {
                                "AddConnection": {
                                    "class": "has_image",
                                    "src": entity_id,
                                    "dst": image_id
                                }
                            }
                        ]
                        
                        db.query(add_image_query)
                        db.query(link_query)
                    except Exception as img_e:
                        print(f"    Warning: Could not store image for email {idx}: {img_e}")
                
                # If email has attachments, store attachment metadata in entity properties
                if email.get("attachments"):
                    for att_idx, attachment in enumerate(email["attachments"]):
                        try:
                            entity_properties[f"attachment_{att_idx}_filename"] = attachment["filename"]
                            entity_properties[f"attachment_{att_idx}_type"] = attachment["content_type"]
                            entity_properties[f"attachment_{att_idx}_size"] = attachment["size"]
                        except Exception as att_e:
                            print(f"    Warning: Could not process attachment {att_idx} for email {idx}: {att_e}")
                
                stored_count += 1
                print(f"  [{idx}/{len(emails)}] Stored email: {email['subject'][:50]}...")
                
            except Exception as e:
                print(f"  [{idx}/{len(emails)}] Error storing email '{email['subject'][:30]}...': {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n✅ Successfully stored {stored_count}/{len(emails)} emails in ApertureData!")
        
    except Exception as e:
        print(f"\n❌ Error storing emails in ApertureData: {e}")
        import traceback
        traceback.print_exc()
        print("Saving emails to JSON file as fallback...")
        save_emails_to_json(emails)
    
    # Also save to JSON as backup
    save_emails_to_json(emails)
    print("\n✅ Sample emails also saved to 'sample_emails.json' as backup")


def save_emails_to_json(emails=None):
    """Save emails to JSON file."""
    if emails is None:
        # Generate emails if not provided
        emails = []
        for i in range(7):
            email = generate_sample_email(
                is_spam=False,
                is_unread=random.choice([True, False]),
                has_image=random.choice([True, False]),
                has_attachment=random.choice([True, False])
            )
            emails.append(email)
        
        for i in range(3):
            email = generate_sample_email(
                is_spam=True,
                is_unread=True,
                has_image=False,
                has_attachment=False
            )
            emails.append(email)
    
    output_file = "sample_emails.json"
    with open(output_file, 'w') as f:
        json.dump(emails, f, indent=2, default=str)
    
    print(f"✅ Saved {len(emails)} emails to {output_file}")


if __name__ == "__main__":
    print("=" * 60)
    print("ApertureData Email Database Setup")
    print("=" * 60)
    setup_aperturedb()
    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
