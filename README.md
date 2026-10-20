# Brahma — AI for Every Phone

Brahma is a multilingual AI voice assistant that makes artificial intelligence accessible through ordinary telephone calls.

Users can speak with Brahma using a basic keypad phone or a smartphone without mobile internet.

## Why Brahma?

Millions of people in India use feature phones or have limited access to mobile internet. Most AI assistants require a smartphone, an application, or an internet connection.

Brahma addresses this accessibility gap by allowing users to interact with AI through regular voice calls.

## Features

- AI conversations through ordinary phone calls
- Kannada and English voice interaction
- Multilingual support through Gemini Live
- Live weather information using Open-Meteo
- Audio streaming through Exotel
- Multiple authorized callers
- Basic Authentication for the WebSocket endpoint

## Technology Stack

- Python
- FastAPI and Uvicorn
- Google Gemini Live API
- AWS EC2
- Exotel Voicebot / AgentStream
- Cloudflare Tunnel
- Open-Meteo API
- NumPy and SciPy
- WebSockets

## Architecture

Phone Call
    |
    v
Exotel Voicebot
    |
    v
Cloudflare Tunnel (WSS)
    |
    v
Brahma FastAPI Gateway (AWS EC2)
    |
    v
Gemini Live API
    |
    v
Spoken Response to Caller

## Security

API credentials, authorized phone numbers, and environment variables are excluded from the repository.

## Project Team

- Shreehari S Kulkarni
- Gandharva C Kulkarni

Both team members contributed to the Brahma project.

## Status

Working prototype demonstrated through real telephone calls.

## Future Scope

- Expand support for regional Indian languages
- Improve access to agricultural and government information
- Support more simultaneous callers
- Deploy a permanent public endpoint
- Optimize reliability and operating costs
