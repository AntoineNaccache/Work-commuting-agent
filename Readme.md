# Overview

We want to build an agent that's able to help someone save time when doing their commute, 
We want the agent to have the following capabilities :
    -Reads your unread emails, filters out spams, creates a summary
    -Communicates with you vocally
    -Access your MSTeams Schedule, read it out to you, suggests new meetings scheduling based on your email inbox.

# MVP(Minimum viable product)

## Emails stored in vectored Database
For now we will assume the emails are already in ApertureData
### Tasks
-Generate emails Database, two ways :
    -Find a Public Emails Database that we can store in ApertureData OR
    -Generate Emails with AI
    -If the integration with apertureData is tough, we can start out with a small databases(Like 10 emails)
### Going further
    -We want the emails to have PDF files attached, videos, mp3s... So that we can leverage the multimodal aspect
    -We want the database to contain spam emails
    -We want the emails to have read/unread labels so that our agents only works on unread emails if asked.

## Previous interractions with agent storage
### Tasks
    -Integrate memory with Memverge so that the agent has memory of previously read emails and user interractions
    -Could help give some context to emails, or upcomming meetings
## Voice support
### Task
    -We want to boot up the conversation with the Agent by giving it a call
    -We want the agent to reply to us vocally, in the back the agent will need to be ble to call to different MCP Tools (for now the Read8email database tool will be enough)

# Going Further

## Scheduling new meetings, or providing suggestions to new meetings
    -We want the agent to be able to suggest new meetings based on the emails that were analysed
    -We want the agent to be able to access the user's schedule, as well as his buisness partners to schedule a meeting on an available time slot
### Main difficulty
We need to have a browsing tool so that our agent uses visions to interract with the user's calendar application

