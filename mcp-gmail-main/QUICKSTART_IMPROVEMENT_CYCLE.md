# Quick Start: MCP Improvement Cycle

> **Get started improving your MCP server in 5 steps**

## What You'll Need

- ✅ Working MCP server
- ✅ MCP client (Claude Desktop, Kilocode, etc.)
- ✅ Claude Code or similar AI assistant
- ⏱️ Time: 30 minutes per cycle

## The 5-Step Process

### Step 1: Use Your MCP Server (10 mins)

**Goal**: Generate real usage data

```bash
# 1. Start your MCP server
cd mcp-gmail-main
python -m mcp_gmail.server

# 2. Open your MCP client (Claude Desktop, Kilocode, etc.)

# 3. Give it real tasks, like:
# - "Schedule calendar events for my flights"
# - "Mark promotional emails as spam"
# - "Find my PGE bills and mark them important"
```

**What to observe**:
- ❌ When does the agent fail?
- 🔄 When does it retry multiple times?
- 🤔 When does the user have to correct it?
- 😤 When does the user express frustration?

**Important**: Let the agent make mistakes! That's valuable data.

---

### Step 2: Locate Conversation Logs (2 mins)

**Log Location**:
```
Windows: %APPDATA%\Code\User\globalStorage\kilocode.kilo-code\tasks\{task-id}\api_conversation_history.json

Mac/Linux: ~/.config/Code/User/globalStorage/kilocode.kilo-code/tasks/{task-id}/api_conversation_history.json
```

**Quick Find** (Windows):
```bash
# Open in Explorer
explorer %APPDATA%\Code\User\globalStorage\kilocode.kilo-code\tasks

# Or use PowerShell
ls "$env:APPDATA\Code\User\globalStorage\kilocode.kilo-code\tasks" | sort LastWriteTime -Descending
```

**What you're looking for**:
- File: `api_conversation_history.json`
- Size: Usually 100KB - 1MB
- Contains: Full conversation between user and agent

---

### Step 3: Analyze with Claude Code (10 mins)

**Option A: Quick Analysis**

Open Claude Code and paste:

```
Check out this log of calling the MCP server with an agent,
identify issues and suggest improvements:

C:\Users\{you}\AppData\Roaming\Code\User\globalStorage\kilocode.kilo-code\tasks\{task-id}\api_conversation_history.json
```

Claude Code will:
1. Read the log file
2. Extract user feedback
3. Identify error patterns
4. Suggest specific improvements

**Option B: Focused Analysis**

For deeper analysis, ask Claude Code:

```
Analyze this MCP conversation log and:
1. Find all user denials and extract their feedback
2. Identify search patterns - what searches were attempted?
3. Count tool call attempts - where did the agent struggle?
4. List all errors encountered
5. Suggest 3 high-priority improvements

Path: {log-path}
```

---

### Step 4: Implement Improvements (5+ mins)

**Common Improvement Patterns**:

#### Pattern 1: User says "Look for X"
```
User: "Look for emails with PDF attachments"
Agent: *uses wrong tool*
User: Denies operation

→ Solution: Create new tool
@mcp.tool()
def search_emails_with_pdf_attachments(...):
    """Search for emails that contain PDF attachments"""
```

#### Pattern 2: Tool fails with error
```
Agent: Uses add_label_to_message
Result: KeyError: 'payload'

→ Solution: Fix the tool
# Get message first, then modify
message = get_message(service, message_id)
headers = get_headers_dict(message)
modify_message_labels(...)
```

#### Pattern 3: User corrects the agent
```
User: "But this flight has already happened"

→ Solution: Add validation
if start_time < now:
    return "⚠️ Warning: This event is in the PAST!"
```

#### Pattern 4: Agent makes same search repeatedly
```
Agent tries 10+ searches to find flights:
- search_emails(subject="flight")
- search_emails(subject="booking")
- search_emails(subject="confirmation")
...

→ Solution: Create specialized search
def search_flight_bookings(...):
    # Smart filtering, excludes promotions
```

**Implementation Tips**:
- Use exact user phrases in tool names
- Add validation before actions
- Show what was checked (transparency)
- Provide clear next steps

---

### Step 5: Test & Repeat (3 mins)

**Quick Tests**:

```bash
# 1. Syntax check
python -m py_compile your_server.py

# 2. Start server
python -m your_server

# 3. Try the same task again
# Does it work better now?
```

**Measure Success**:
- ✅ Fewer tool calls to complete task
- ✅ No errors where there were errors before
- ✅ User doesn't need to correct the agent
- ✅ Task completes on first try

**Iterate**:
- Use the improved server
- Generate new logs
- Analyze again
- Find new improvements

---

## Real Example

### Cycle 1: Initial Use

```
User: "Mark promotional emails as spam"
Agent: *marks 10 emails*
User: "But you didn't check their content first!"

User: "Schedule my flight"
Agent: *creates event for November 1st*
User: "But that flight already happened!"
```

**Log Analysis Found**:
1. ❌ No content verification before actions
2. ❌ No past date validation
3. ❌ Agent confused price alerts with bookings

### Cycle 2: After Improvements

```python
# Added: Content reading reminder
get_emails.__doc__ += """
⚠️ IMPORTANT: Always use this to examine email
content before taking actions
"""

# Added: Date validation
def schedule_meeting(...):
    if start_time < now:
        return "⚠️ Warning: This event is in the PAST!"

# Added: Smart search
def search_flight_bookings(...):
    query = '(booking OR ticket) -(price OR deal)'
```

### Cycle 3: Testing

```
User: "Mark promotional emails as spam"
Agent: *reads emails first*
Agent: *marks only promotional ones*
✅ Success!

User: "Schedule my flight"
Agent: *extracts date from email*
Agent: "⚠️ Warning: This event is in the PAST!"
✅ Prevented error!
```

---

## Pro Tips

### 🎯 Focus on User Language

If user says "look for PDFs", create `search_pdfs()`, not `find_attachments_of_type()`

### 📊 Track Metrics

Keep a simple log:
```
Cycle 1: 30 tool calls → task completed
Cycle 2: 8 tool calls → task completed (73% improvement!)
Cycle 3: 1 tool call → task completed (97% improvement!!)
```

### 🔍 Look for Patterns Across Logs

If 3 different users ask about PDFs, that's a high-priority feature!

### ⚡ Start Small

Don't try to fix everything at once. Pick the top 1-3 issues per cycle.

### 📝 Document Everything

Keep notes on:
- What was the issue?
- What user feedback indicated it?
- What was the fix?
- Did it work?

---

## Automation Ideas

### Level 1: Script Log Extraction
```python
# auto_extract_logs.py
import json
from pathlib import Path

logs_dir = Path.home() / "AppData/Roaming/Code/User/globalStorage/kilocode.kilo-code/tasks"
latest_log = max(logs_dir.glob("*/api_conversation_history.json"), key=lambda p: p.stat().st_mtime)
print(f"Latest log: {latest_log}")
```

### Level 2: Automated Issue Detection
```python
# detect_issues.py
def analyze_log(log_path):
    issues = []

    # Find denials
    for msg in log['messages']:
        if 'denied' in msg.get('content', ''):
            issues.append({
                'type': 'user_denial',
                'feedback': extract_feedback(msg)
            })

    # Find errors
    # Find repeated searches
    # etc.

    return issues
```

### Level 3: AI-Powered Analysis Agent
```python
# analysis_agent.py
from anthropic import Anthropic

def analyze_with_ai(log_path):
    with open(log_path) as f:
        log_content = f.read()

    client = Anthropic()
    analysis = client.messages.create(
        model="claude-sonnet-4",
        messages=[{
            "role": "user",
            "content": f"""
            Analyze this MCP conversation log and identify issues:
            {log_content}

            Return JSON with:
            - issues found
            - suggested improvements
            - priority ranking
            """
        }]
    )

    return analysis
```

---

## Common Pitfalls

### ❌ Not Using Real Tasks
**Bad**: "Test the server with dummy data"
**Good**: "Use it for actual work you need done"

### ❌ Ignoring Small Frustrations
**Bad**: "It works eventually, good enough"
**Good**: "Why did it take 3 tries? Let's fix that"

### ❌ Not Tracking Changes
**Bad**: Making changes without documenting what/why
**Good**: Keep IMPROVEMENTS_SUMMARY.md updated

### ❌ Over-Engineering
**Bad**: Building complex analysis pipeline before testing
**Good**: Start manual, automate what's painful

---

## Success Metrics

You're doing it right when:

- ✅ Each cycle reduces tool calls needed
- ✅ User corrections decrease over time
- ✅ New users make fewer mistakes
- ✅ Common tasks become one-shot operations
- ✅ Error rates drop with each iteration

---

## Next Steps

1. **Run Cycle 1 today**
   - Use server for 10 minutes
   - Analyze logs
   - Make 1 improvement

2. **Share your results**
   - What issues did you find?
   - What improvements worked best?
   - What surprised you?

3. **Build automation incrementally**
   - Start with log extraction
   - Add issue detection
   - Eventually: full AI analysis

4. **Join the conversation**
   - Share your improvement workflow
   - Learn from others' patterns
   - Contribute back to the ecosystem

---

## Resources

- [**Full Workflow Documentation**](MCP_IMPROVEMENT_WORKFLOW.md)
- [**Improvements Summary**](IMPROVEMENTS_SUMMARY.md)
- [**Example Log Analysis**](example_log_analysis.md) (coming soon)
- [**Automation Scripts**](automation/) (coming soon)

---

**Ready to start?** Pick a task, use your MCP server, and analyze the logs. You'll be amazed at what you find! 🚀
