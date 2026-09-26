# Reel2Short — Implementation Specification

**Version:** 2.0
**Status:** MVP Ready for Implementation
**Last Updated:** September 2026
**Development Environment:** VS Code + Antigravity
**Architecture:** Local-first Web Application

---

# 1. Product Overview

## Product Name

**Reel2Short**

---

## Product Goal

Reel2Short is a web application that helps a creator take videos from their own Instagram account, prepare them for YouTube Shorts, generate optimized metadata using AI, and upload them to their YouTube channel.

The application supports two video acquisition paths:

### Path A — Automatic Instagram Download

```text
Instagram Creator Account
        ↓
Instagram API
        ↓
Fetch User's Reels
        ↓
media_url Available
        ↓
Download Video
```

### Path B — Manual Video Upload

```text
Instagram Creator Account
        ↓
Fetch User's Reels
        ↓
media_url Unavailable
        ↓
Show Manual Upload UI
        ↓
User Uploads Original Video
```

After the video is available:

```text
Video
  ↓
Check Aspect Ratio
  ↓
Convert if Required
  ↓
User Provides Description + Keywords
  ↓
AI Generates Metadata
  ↓
User Reviews + Edits
  ↓
YouTube Upload
  ↓
Private by Default
```

---

# 2. Core User Flow

The complete MVP workflow:

```text
START

  ↓

Connect Instagram

  ↓

Fetch Reels

  ↓

Select Reel

  ↓

Is media_url available?

  │
  ├──── YES
  │
  │       ↓
  │
  │   Download Video
  │
  │
  └──── NO
          │
          ↓
    Manual Upload
          │

          ↓

      Video Ready

          ↓

   Check Aspect Ratio

          │
          │
    ┌─────┴──────┐
    │            │
Vertical      Horizontal
    │            │
    │            ↓
    │     Conversion Options
    │            │
    │     ┌──────┴──────┐
    │     │             │
    │   Crop       Blur Background
    │
    └─────────────┬──────────────┘
                  │
                  ↓

             Video Ready

                  ↓

        Description + Keywords

                  ↓

              AI Generate

                  ↓

       Review + Edit Metadata

                  ↓

           Connect YouTube

                  ↓

            Upload Video

                  ↓

         PRIVATE by Default

                  ↓

              COMPLETED
```

---

# 3. Product Scope

## Version 1 — MVP

The application MUST support:

### Instagram

* Connect Instagram account.
* Fetch user's own media.
* Filter Reels.
* Display Reels.
* Display thumbnails.
* Display captions.
* Display dates.
* Select a Reel.
* Download Reel when `media_url` is available.
* Detect when `media_url` is unavailable.
* Show manual upload fallback.

---

### Video

* Store downloaded videos locally.
* Allow manual video upload.
* Support MP4.
* Support MOV.
* Detect aspect ratio.
* Detect basic video metadata.
* Allow horizontal video conversion.
* Allow preview before YouTube upload.

---

### Horizontal Video Conversion

Support:

#### Option 1

```text
Crop to Vertical
```

#### Option 2

```text
Blurred Background
```

#### Option 3

```text
Upload as Regular Video
```

---

### AI

User provides:

* Description.
* Keywords.

AI generates:

* Multiple title suggestions.
* YouTube description.
* Hashtags.
* Tags.
* Category suggestion.
* Hook suggestion.

---

### YouTube

* Google OAuth.
* Connect YouTube account.
* Upload video.
* Edit metadata before upload.
* Private upload by default.
* Upload progress.
* Success confirmation.
* Error reporting.

---

# 4. Explicitly NOT Included in MVP

Do NOT implement initially:

```text
Automatic Video AI Analysis

OCR

Automatic Speech Recognition

Transcript Generation

Face Detection

Object Detection

Smart Subject Tracking

AI Thumbnail Generation

AI Content Score

YouTube Analytics

Scheduling

Batch Upload

Automatic Publishing

Instagram Scraping

Browser Automation

Third-Party Reel Downloaders
```

These may be added later.

---

# 5. Product Rules

## Instagram Rule

Use official Meta APIs only.

Do NOT:

```text
Scrape Instagram

Bypass Meta restrictions

Extract hidden video URLs

Use browser automation

Download media belonging to other users
```

If Instagram does not provide:

```text
media_url
```

the application MUST show:

```text
Automatic download is unavailable for this Reel.

Please upload the original video to continue.
```

---

# 6. YouTube Shorts Rules

The application should prepare videos for YouTube Shorts.

Preferred format:

```text
Aspect Ratio

9:16
```

Recommended output:

```text
1080 × 1920
```

The application should not attempt to force a video to become a Short through metadata.

The uploaded file determines its format classification.

For MVP:

```text
Vertical
↓
Upload directly

Square
↓
Allow upload

Horizontal
↓
Offer conversion to vertical

Horizontal
↓
Optional regular YouTube upload
```

---

# 7. Technology Stack

## Backend

```text
Python 3.13

FastAPI

Uvicorn

Pydantic

SQLAlchemy

SQLite

HTTPX

python-dotenv
```

---

## Frontend

```text
React

TypeScript

Vite

Tailwind CSS
```

---

## Video Processing

```text
FFmpeg

ffprobe
```

Only use them for:

```text
Basic Video Metadata

Aspect Ratio Detection

Horizontal → Vertical Conversion

Video Preview Support
```

Do NOT build an unnecessary video processing pipeline.

---

## External APIs

### Instagram

```text
Official Instagram API

Instagram Login
```

---

### YouTube

```text
YouTube Data API v3

Google OAuth 2.0
```

---

### AI

Initial provider:

```text
Configurable AI Provider
```

Recommended first implementation:

```text
Gemini
```

The AI provider and model MUST NOT be hardcoded throughout the application.

---

# 8. Architecture

```text
                    React Frontend

                          │

                          ▼

                    FastAPI Backend

                          │

          ┌───────────────┼───────────────┐

          │               │               │

          ▼               ▼               ▼

     Instagram API      AI API        YouTube API

          │               │               │

          └───────────────┼───────────────┘

                          │

                          ▼

                    Application

                          │

             ┌────────────┴────────────┐

             │                         │

             ▼                         ▼

         SQLite                  Local Storage
```

---

# 9. Local-First Architecture

The MVP must run locally.

No cloud deployment required.

No Docker required initially.

Videos should be stored locally.

Structure:

```text
storage/

├── downloads/

├── uploads/

├── converted/

├── temp/
```

---

# 10. Project Structure

```text
Reel2Short/

├── backend/
│
│   ├── app/
│   │
│   │   ├── main.py
│   │
│   │   ├── config.py
│   │
│   │   ├── database.py
│   │
│   │   ├── api/
│   │   │
│   │   │   ├── health.py
│   │   │
│   │   │   ├── instagram.py
│   │   │
│   │   │   ├── videos.py
│   │   │
│   │   │   ├── ai.py
│   │   │
│   │   │   ├── youtube.py
│   │   │
│   │   │   └── auth.py
│   │
│   │   ├── services/
│   │   │
│   │   │   ├── instagram_service.py
│   │   │
│   │   │   ├── download_service.py
│   │   │
│   │   │   ├── video_service.py
│   │   │
│   │   │   ├── ai_service.py
│   │   │
│   │   │   └── youtube_service.py
│   │
│   │   ├── schemas/
│   │   │
│   │   │   ├── instagram.py
│   │   │
│   │   │   ├── video.py
│   │   │
│   │   │   ├── ai.py
│   │   │
│   │   │   └── youtube.py
│   │
│   │   ├── models/
│   │   │
│   │   │   ├── video_asset.py
│   │   │
│   │   │   ├── youtube_upload.py
│   │   │
│   │   │   └── oauth_account.py
│   │
│   │   └── utils/
│
│
├── frontend/
│
│   ├── src/
│   │
│   │   ├── pages/
│   │
│   │   ├── components/
│   │
│   │   ├── services/
│   │
│   │   ├── hooks/
│   │
│   │   ├── types/
│   │
│   │   └── utils/
│
│
├── storage/
│
│   ├── downloads/
│
│   ├── uploads/
│
│   ├── converted/
│
│   └── temp/
│
│
├── .env
│
├── .env.example
│
├── .gitignore
│
├── README.md
│
└── IMPLEMENTATION_SPEC.md
```

---

# 11. Environment Setup

Python version:

```text
Python 3.13
```

Create virtual environment:

```powershell
py -3.13 -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Always install packages using:

```powershell
python -m pip
```

Avoid global package installation.

---

# 12. Required Software

Verify:

```text
Python

Node.js

npm

Git

FFmpeg

ffprobe
```

Commands:

```powershell
python --version
```

```powershell
node -v
```

```powershell
npm -v
```

```powershell
git --version
```

```powershell
ffmpeg -version
```

```powershell
ffprobe -version
```

---

# 13. Environment Variables

Create:

```text
.env
```

Example:

```env
APP_ENV=development

APP_HOST=127.0.0.1

APP_PORT=8000


DATABASE_URL=sqlite:///./reel2short.db


INSTAGRAM_APP_ID=

INSTAGRAM_APP_SECRET=

INSTAGRAM_REDIRECT_URI=


GOOGLE_CLIENT_ID=

GOOGLE_CLIENT_SECRET=

GOOGLE_REDIRECT_URI=


AI_PROVIDER=gemini

AI_API_KEY=

AI_MODEL=


STORAGE_DIR=./storage
```

---

# 14. Environment Example

Create:

```text
.env.example
```

Example:

```env
APP_ENV=development

APP_HOST=127.0.0.1

APP_PORT=8000

DATABASE_URL=sqlite:///./reel2short.db

INSTAGRAM_APP_ID=

INSTAGRAM_APP_SECRET=

INSTAGRAM_REDIRECT_URI=

GOOGLE_CLIENT_ID=

GOOGLE_CLIENT_SECRET=

GOOGLE_REDIRECT_URI=

AI_PROVIDER=gemini

AI_API_KEY=

AI_MODEL=

STORAGE_DIR=./storage
```

Never include actual secrets.

---

# 15. Security Rules

Never commit:

```text
.env

API keys

Access tokens

Refresh tokens

OAuth secrets

Downloaded videos

Uploaded videos

Database files
```

---

# 16. Git Ignore

```text
.env

.venv/

__pycache__/

*.pyc

storage/

*.db

tokens/

credentials/

.pytest_cache/
```

---

# 17. Instagram Integration

Create:

```text
InstagramService
```

Responsibilities:

```text
OAuth

Token Management

Fetch Media

Pagination

Filter Reels

Normalize API Responses
```

---

# 18. Instagram Media Model

Normalize Instagram data.

```python
class InstagramMedia:

    id: str

    media_type: str

    media_product_type: str | None

    media_url: str | None

    thumbnail_url: str | None

    permalink: str | None

    caption: str | None

    timestamp: str | None
```

The application must tolerate missing fields.

---

# 19. Reel Detection

Treat media as a Reel when:

```text
media_type == VIDEO
```

and:

```text
media_product_type == REELS
```

Do not assume every API response contains every field.

---

# 20. Instagram Reels UI

Display:

```text
Thumbnail

Caption

Date

Media Status

Use Reel Button
```

Example:

```text
┌─────────────────────┐

│                     │

│      Thumbnail      │

│                     │

└─────────────────────┘


Caption:

Wait for the end 😋


Date:

August 28, 2026


[ Use This Reel ]
```

---

# 21. Video Acquisition

Create:

```text
DownloadService
```

Workflow:

```text
media_url Available

        ↓

Download Video

        ↓

Temporary File

        ↓

Validate

        ↓

Move to Storage

        ↓

Video Ready
```

---

# 22. Video Download Requirements

Support:

```text
HTTP Streaming

Timeout

Retry

Temporary File

Cleanup

Download Errors
```

Do not load large videos entirely into memory.

---

# 23. Missing media_url

If:

```text
media_url == None
```

Return:

```json
{
  "download_available": false,

  "manual_upload_required": true
}
```

Frontend displays:

```text
Automatic download is unavailable
for this Reel.

Upload the original video
to continue.
```

---

# 24. Manual Video Upload

Accept initially:

```text
.mp4

.mov
```

Frontend:

```text
Upload Original Video

[ Choose Video ]

Supported:

MP4

MOV
```

---

# 25. Video Asset

Every acquired video should become a common internal object.

```python
class VideoAsset:

    id: str

    source: str

    source_media_id: str | None

    source_url: str | None

    file_path: str

    original_filename: str

    width: int

    height: int

    duration_seconds: float
```

Source values:

```text
instagram

manual
```

---

# 26. Video Metadata

Use:

```text
ffprobe
```

to obtain:

```text
width

height

duration

format
```

Do not build complex video analysis.

---

# 27. Aspect Ratio Detection

Calculate:

```text
width / height
```

Classify:

```text
VERTICAL

SQUARE

HORIZONTAL
```

Example:

```text
1080 × 1920

↓

VERTICAL
```

---

Example:

```text
1920 × 1080

↓

HORIZONTAL
```

---

# 28. Vertical Video

If video is vertical:

```text
Upload Directly
```

Example:

```text
1080 × 1920
```

---

# 29. Square Video

If video is square:

```text
Allow Upload
```

Example:

```text
1080 × 1080
```

Do not unnecessarily convert square video.

---

# 30. Horizontal Video

If video is horizontal:

```text
1920 × 1080
```

Display:

```text
Your video is horizontal.

Choose how you want to upload it.
```

Options:

```text
○ Convert to Vertical

  Crop Video


○ Convert to Vertical

  Blurred Background


○ Upload as Regular YouTube Video
```

---

# 31. Horizontal Conversion

Create:

```text
VideoService
```

Responsibilities:

```text
Inspect Video

Detect Aspect Ratio

Convert Horizontal Video

Manage Output Files
```

---

# 32. Crop Conversion

Workflow:

```text
1920 × 1080

        ↓

Center Crop

        ↓

Vertical Output

        ↓

1080 × 1920
```

The MVP uses center crop.

Do NOT implement:

```text
Face Tracking

Object Tracking

AI Subject Detection
```

These are future features.

---

# 33. Blurred Background Conversion

Recommended MVP conversion.

Workflow:

```text
Original Horizontal Video

        ↓

Scale Video

        ↓

Create Vertical Canvas

        ↓

Background:

Blurred Original Video

        ↓

Foreground:

Original Video

        ↓

Vertical Output
```

Output:

```text
1080 × 1920
```

This preserves the entire horizontal video.

---

# 34. FFmpeg Responsibilities

FFmpeg should ONLY be responsible for:

```text
Horizontal → Vertical Conversion

Crop Conversion

Blurred Background Conversion
```

Do NOT use FFmpeg for unnecessary processing.

---

# 35. Video Preview

After conversion:

```text
Original Video

        ↓

Converted Video

        ↓

Preview
```

Frontend:

```text
Original

[ Video Preview ]


Converted

[ Video Preview ]


[ Continue ]

[ Change Conversion ]
```

---

# 36. AI Metadata Generation

The AI system should be simple.

The user provides context.

The AI improves metadata.

The AI does NOT need to analyze the actual video in MVP.

---

# 37. AI User Input

The frontend collects:

## Description

Example:

```text
Funny reel about Microsoft Teams
not working properly while working
from home as a software developer.
```

---

## Keywords

Example:

```text
software developer

Microsoft Teams

work from home

developer life

funny
```

---

## Optional Content Type

Examples:

```text
Travel

Food

Technology

Funny

Lifestyle

Motorcycle

Vlog

Educational
```

---

# 38. AI Input

Send:

```json
{
  "description": "",

  "keywords": [],

  "content_type": "",

  "platform": "youtube_shorts"
}
```

---

# 39. AI Output

Generate:

```text
Title Suggestions

Description

Hashtags

Tags

Category Suggestion

Hook Suggestion
```

---

# 40. AI Title Generation

Generate:

```text
5 Title Suggestions
```

Recommended styles:

```text
Curiosity

Search Friendly

Funny

Emotional

Simple
```

Example:

```text
Why Does Microsoft Teams Even Have This Feature? 😭
```

---

# 41. AI Description

Generate:

```text
Short Description

Relevant Context

Natural Keywords

Relevant Hashtags
```

Do not keyword stuff.

---

# 42. Hashtags

Generate:

```text
3 to 8 Relevant Hashtags
```

Example:

```text
#SoftwareDeveloper

#DeveloperLife

#WFH

#Programming

#FunnyShorts
```

---

# 43. Tags

Generate relevant tags.

Example:

```text
software developer

developer life

work from home

Microsoft Teams

coding

programming
```

Do not generate irrelevant tags.

---

# 44. Category Suggestion

AI suggests a YouTube category.

Examples:

```text
Travel

Entertainment

Comedy

Education

Science and Technology

People and Blogs
```

The user can override the suggestion.

---

# 45. Hook Suggestion

AI suggests a short hook.

Example:

```text
Every software developer
has faced this problem 😭
```

The user can:

```text
Use

Edit

Ignore
```

---

# 46. AI Output Schema

The backend must validate AI output.

Example:

```json
{
  "titles": [

    {
      "text": "",

      "style": ""
    }

  ],

  "description": "",

  "hashtags": [],

  "tags": [],

  "category": "",

  "hook": ""
}
```

Use Pydantic validation.

---

# 47. AI Provider Architecture

Create:

```text
AIService
```

The provider must be configurable.

Example:

```env
AI_PROVIDER=gemini
```

Future providers may include:

```text
OpenAI

Other providers
```

Do not tightly couple application logic to one AI provider.

---

# 48. AI Rules

AI MUST NOT:

```text
Guarantee Views

Guarantee Virality

Invent Video Content

Invent People

Invent Locations

Generate Misleading Metadata

Keyword Stuff
```

AI SHOULD:

```text
Generate Accurate Metadata

Generate Multiple Title Options

Use User Keywords Naturally

Keep Metadata Relevant

Provide Useful Suggestions
```

---

# 49. Metadata Review

AI output is NEVER automatically uploaded.

The user must review.

Frontend:

```text
TITLE

[ Editable Input ]


DESCRIPTION

[ Editable Text Area ]


HASHTAGS

[ Editable ]


TAGS

[ Editable ]


CATEGORY

[ Dropdown ]


HOOK

[ Editable ]


[ Continue to YouTube ]
```

---

# 50. YouTube OAuth

Use:

```text
Google OAuth 2.0
```

Required permission:

```text
YouTube Upload Access
```

Responsibilities:

```text
OAuth Redirect

Callback

Token Storage

Connection Status
```

Never expose tokens to the frontend.

---

# 51. YouTube Connection UI

Display:

```text
YouTube Account

Status:

Not Connected


[ Connect YouTube ]
```

After connection:

```text
YouTube Account

Status:

Connected


[ Change Account ]
```

---

# 52. YouTube Upload

Create:

```text
YouTubeService
```

Responsibilities:

```text
Upload Video

Send Metadata

Send Tags

Set Privacy

Track Upload Status

Handle Errors
```

---

# 53. YouTube Upload Settings

Before upload:

```text
Video

Title

Description

Tags

Category

Privacy
```

Privacy options:

```text
Private

Unlisted

Public
```

Default:

```text
Private
```

---

# 54. Upload UI

```text
────────────────────

VIDEO

video.mp4


TITLE

[ Why Does Microsoft Teams... ]


DESCRIPTION

[ Editable Description ]


TAGS

[ software developer ]

[ WFH ]

[ funny ]


CATEGORY

[ Comedy ▼ ]


PRIVACY

● Private

○ Unlisted

○ Public


[ Upload to YouTube ]

────────────────────
```

---

# 55. Upload States

Use:

```text
PENDING

UPLOADING

UPLOADED

FAILED
```

Frontend:

```text
Uploading...

████████░░░░░░░

65%
```

---

# 56. Upload Success

Display:

```text
✓ Video Uploaded Successfully


Title:

Why Does Microsoft Teams....


Privacy:

Private


YouTube Video ID:

XXXXXXXX


[ Open in YouTube ]

[ Upload Another ]
```

---

# 57. Error Handling

Errors must be actionable.

Bad:

```text
500 Error
```

Good:

```text
Instagram did not provide
a downloadable video URL.

Upload the original video
to continue.
```

---

# 58. Common Errors

Handle:

```text
Instagram Token Expired

Instagram API Error

Media URL Missing

Video Download Failed

Invalid Video File

Video Conversion Failed

AI Request Failed

Invalid AI Response

YouTube OAuth Failed

YouTube Upload Failed
```

---

# 59. Error Response Structure

Backend:

```json
{
  "success": false,

  "error": {

    "code": "",

    "message": "",

    "action": ""
  }
}
```

Example:

```json
{
  "success": false,

  "error": {

    "code": "MEDIA_URL_UNAVAILABLE",

    "message": "Instagram did not provide a downloadable video URL.",

    "action": "UPLOAD_ORIGINAL_VIDEO"
  }
}
```

---

# 60. Database

Use:

```text
SQLite
```

MVP tables:

```text
video_assets

ai_metadata

youtube_uploads

oauth_accounts
```

Keep database design simple.

---

# 61. Video Assets

Store:

```text
id

source

source_media_id

source_url

file_path

original_filename

width

height

duration_seconds

created_at
```

---

# 62. AI Metadata Table

Store:

```text
id

video_asset_id

description_input

keywords_input

content_type

titles

description

hashtags

tags

category

hook

created_at
```

---

# 63. YouTube Upload Table

Store:

```text
id

video_asset_id

youtube_video_id

title

privacy

status

error_message

created_at
```

---

# 64. OAuth Accounts

Store:

```text
id

provider

account_identifier

access_token

refresh_token

expires_at
```

Tokens must not be exposed through APIs.

---

# 65. Backend API

## Health

```text
GET

/health
```

---

# 66. Instagram

```text
GET

/auth/instagram
```

---

```text
GET

/auth/instagram/callback
```

---

```text
GET

/instagram/media
```

---

# 67. Video Download

```text
POST

/videos/download/{media_id}
```

---

# 68. Manual Upload

```text
POST

/videos/upload
```

---

# 69. Video Details

```text
GET

/videos/{video_id}
```

---

# 70. Video Conversion

```text
POST

/videos/{video_id}/convert
```

Request:

```json
{
  "mode": "crop"
}
```

or:

```json
{
  "mode": "blur_background"
}
```

---

# 71. AI Metadata

```text
POST

/videos/{video_id}/generate-metadata
```

Request:

```json
{
  "description": "",

  "keywords": [],

  "content_type": ""
}
```

---

# 72. YouTube OAuth

```text
GET

/auth/youtube
```

---

```text
GET

/auth/youtube/callback
```

---

# 73. YouTube Upload

```text
POST

/videos/{video_id}/youtube-upload
```

Request:

```json
{
  "title": "",

  "description": "",

  "tags": [],

  "category": "",

  "privacy": "private"
}
```

---

# 74. Frontend Pages

## Page 1

Dashboard.

---

# 75. Dashboard

Display:

```text
Reel2Short


Instagram

✓ Connected


YouTube

✓ Connected


[ Browse Instagram Reels ]


[ Upload Video ]
```

---

# 76. Page 2

Instagram Reels.

Display:

```text
Reel Grid


Thumbnail

Caption

Date


[ Use Reel ]
```

---

# 77. Page 3

Video Acquisition.

If downloadable:

```text
Downloading Reel...

██████████

Complete ✓
```

---

If unavailable:

```text
Automatic Download Unavailable


Upload Original Video


[ Choose Video ]
```

---

# 78. Page 4

Video Format.

Vertical:

```text
✓ Video is Vertical

Recommended for YouTube Shorts


[ Continue ]
```

---

Horizontal:

```text
Your video is Horizontal


Choose Format:


○ Crop to Vertical


○ Blurred Background


○ Upload as Regular Video


[ Continue ]
```

---

# 79. Page 5

Video Preview.

Display:

```text
Video Preview


Resolution:

1080 × 1920


Duration:

31 Seconds


Format:

Vertical


[ Continue to AI ]
```

---

# 80. Page 6

AI Metadata.

Input:

```text
Describe Your Video


[ Text Area ]


Keywords


[ Keyword Input ]


Content Type


[ Dropdown ]


[ Generate Metadata ]
```

---

# 81. Page 7

Metadata Review.

Display:

```text
Title Suggestions


○ Title 1

○ Title 2

○ Title 3

○ Title 4

○ Title 5


Description

[ Editable ]


Hashtags

[ Editable ]


Tags

[ Editable ]


Category

[ Dropdown ]


Hook

[ Editable ]


[ Continue ]
```

---

# 82. Page 8

YouTube Upload.

Display:

```text
Ready to Upload


Video

✓ Ready


Metadata

✓ Ready


YouTube

✓ Connected


Privacy


● Private

○ Unlisted

○ Public


[ Upload to YouTube ]
```

---

# 83. Page 9

Upload Status.

```text
Uploading...


████████████░░


80%


Please wait...
```

---

# 84. Page 10

Success.

```text
✓ Upload Successful


Your video has been uploaded.


Privacy:

Private


[ Open YouTube ]


[ Create Another ]
```

---

# 85. Frontend Principles

UI should be:

```text
Simple

Minimal

Creator Friendly

Step-by-Step

Clear

Mobile Friendly
```

Do NOT over-design.

---

# 86. Backend Principles

Backend should be:

```text
Simple

Modular

Typed

Testable

Secure
```

Do NOT introduce microservices.

Do NOT introduce unnecessary queues.

Do NOT introduce Docker unless needed later.

---

# 87. Logging

Log:

```text
Request

Operation

Success

Failure
```

Example:

```text
Instagram media fetched

Media ID:

123


Download started


Download completed


Video conversion started


AI metadata generated


YouTube upload started


YouTube upload completed
```

Never log:

```text
API Keys

Access Tokens

Refresh Tokens

Client Secrets
```

---

# 88. Testing

## Unit Tests

Test:

```text
Instagram Response Parsing

Reel Filtering

Missing media_url

Video Aspect Detection

Crop Conversion Request

Blur Conversion Request

AI Response Validation

YouTube Metadata Mapping
```

---

# 89. Integration Tests

Test:

```text
Instagram Media Fetch

Video Download

Manual Upload

Video Conversion

AI Generation

Google OAuth

YouTube Upload
```

Use mocks when credentials are unavailable.

---

# 90. Development Phases

---

# Phase 0

## Repository Inspection

Before writing major code:

Inspect:

```text
Existing Files

Existing Instagram Code

Existing Video Download Code

Environment

Dependencies

Current Project Structure
```

Do not rewrite working code.

---

## Phase 0 Report

Provide:

```text
FILES DISCOVERED

EXISTING FUNCTIONALITY

WORKING CODE

MISSING PREREQUISITES

ENVIRONMENT STATUS

DEPENDENCY STATUS

RISKS

PHASE 1 PLAN
```

---

# Phase 1

## Backend Foundation

Implement:

```text
FastAPI

Configuration

Environment Variables

SQLite

Health Endpoint

Storage Directories
```

---

# Phase 2

## Instagram

Implement:

```text
Instagram OAuth

Media Fetching

Reel Filtering

Reel UI API
```

Preserve existing working code.

---

# Phase 3

## Video Acquisition

Implement:

```text
Download Video

Store Video

Manual Upload

Video Asset
```

Support:

```text
media_url available

media_url unavailable
```

---

# Phase 4

## Video Format

Implement:

```text
ffprobe Metadata

Aspect Ratio Detection

Vertical Detection

Square Detection

Horizontal Detection
```

---

# Phase 5

## Horizontal Conversion

Implement:

```text
Center Crop

Blurred Background

Output Storage

Video Preview
```

Use FFmpeg.

---

# Phase 6

## AI Metadata

Implement:

```text
AI Provider Configuration

AI Service

Prompt Construction

Structured Output

Pydantic Validation
```

Generate:

```text
Titles

Description

Hashtags

Tags

Category

Hook
```

---

# Phase 7

## YouTube

Implement:

```text
Google OAuth

YouTube Connection

Video Upload

Metadata Upload

Private Default

Upload Status
```

---

# Phase 8

## Frontend

Implement:

```text
Dashboard

Instagram Reels

Video Acquisition

Video Format

Video Preview

AI Metadata

Metadata Review

YouTube Upload

Success
```

---

# Phase 9

## Testing and Reliability

Implement:

```text
Error Handling

Retry Where Appropriate

Cleanup Temporary Files

Tests

Logging
```

---

# Phase 10

## End-to-End Testing

Test:

```text
Instagram

↓

Select Reel

↓

media_url Available?

      │

YES ──┤── Download

      │

NO ───┤── Manual Upload

      │

      ↓

Video Ready

      ↓

Check Aspect Ratio

      ↓

Convert if Required

      ↓

AI Metadata

      ↓

User Edit

      ↓

YouTube Upload

      ↓

SUCCESS
```

---

# 91. Antigravity Agent Rules

The implementation agent MUST:

1. Read this entire specification first.
2. Inspect existing code before modifying it.
3. Preserve working Instagram integration.
4. Preserve working video download functionality.
5. Implement one phase at a time.
6. Test after every phase.
7. Avoid unnecessary dependencies.
8. Keep secrets backend-only.
9. Never implement Instagram scraping.
10. Never bypass Meta restrictions.
11. Keep AI configurable.
12. Keep YouTube uploads private by default.
13. Use FFmpeg only where required.
14. Do not over-engineer the application.
15. Do not introduce unnecessary services.
16. Do not delete working files without justification.
17. Keep APIs typed.
18. Use Pydantic schemas.
19. Provide clear errors.
20. Update documentation when setup changes.

---

# 92. Phase Completion Report

After every phase, report:

```text
PHASE COMPLETED


FILES CREATED


FILES MODIFIED


DEPENDENCIES ADDED


FUNCTIONALITY IMPLEMENTED


TESTS RUN


TEST RESULTS


KNOWN ISSUES


NEXT PHASE
```

---

# 93. MVP Acceptance Criteria

The MVP is complete when:

## Instagram

```text
✓ Instagram Account Connects

✓ Reels Are Fetched

✓ Reels Are Displayed

✓ Reel Can Be Selected

✓ media_url Is Detected
```

---

## Video

```text
✓ Download Works When media_url Exists

✓ Manual Upload Works When Missing

✓ MP4 Works

✓ MOV Works

✓ Aspect Ratio Detected

✓ Vertical Video Works

✓ Square Video Works

✓ Horizontal Video Detected

✓ Crop Conversion Works

✓ Blur Conversion Works

✓ Converted Video Preview Works
```

---

## AI

```text
✓ Description Input

✓ Keywords Input

✓ Content Type Input

✓ 5 Title Suggestions

✓ Description Generated

✓ Hashtags Generated

✓ Tags Generated

✓ Category Suggested

✓ Hook Suggested

✓ User Can Edit Everything
```

---

## YouTube

```text
✓ Google OAuth Works

✓ YouTube Connects

✓ Video Upload Works

✓ Metadata Upload Works

✓ Private Is Default

✓ User Can Select Privacy

✓ Upload Status Is Displayed

✓ Success Is Confirmed
```

---

# 94. Explicit MVP Success Scenario

A user should be able to:

```text
1.

Open Reel2Short


2.

Connect Instagram


3.

See Their Own Reels


4.

Select a Reel


5.

Download Video

OR

Upload Original Video


6.

Check Video Format


7.

Convert Horizontal Video if Needed


8.

Preview Video


9.

Enter Description


10.

Enter Keywords


11.

Generate Metadata


12.

Select Title


13.

Edit Description


14.

Edit Tags


15.

Connect YouTube


16.

Choose Private


17.

Upload


18.

Receive Success Confirmation
```

---

# 95. Future Features

These features are intentionally postponed.

---

## Version 2

```text
Automatic Subtitles

Transcript Generation

Batch Processing

Multiple AI Providers

Multiple YouTube Accounts

Scheduling
```

---

## Version 3

```text
Smart Subject Tracking

AI Video Understanding

OCR

Thumbnail Suggestions

Face Detection

Object Detection
```

---

## Version 4

```text
YouTube Analytics

View Analysis

Retention Analysis

Title Comparison

Metadata Performance

Recommendation Learning
```

---

# 96. Final Product Philosophy

The application should remain simple.

Core product:

```text
Instagram

OR

Manual Upload

↓

Video

↓

Format Conversion

↓

User Context

↓

AI Metadata

↓

User Review

↓

YouTube Upload
```

The MVP does NOT need to be an AI video editor.

The MVP is a:

```text
Creator Workflow Automation Tool
```

The product should solve one problem well:

> Take a creator's video, prepare it for YouTube Shorts, generate useful metadata, and upload it to YouTube with minimal manual work.

---

# 97. Final Architecture Principle

Build the core workflow first.

```text
Video Acquisition

↓

Video Preparation

↓

Metadata Generation

↓

YouTube Upload
```

AI enhances the workflow.

AI should not block the workflow.

The user should always have control.

The user should always be able to:

```text
Edit

Override

Skip Suggestions
```

before uploading.

---

# END OF IMPLEMENTATION SPECIFICATION
