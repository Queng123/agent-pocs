# POC-2

## Description

This is a proof of concept that an agent search and load the given website, using a google search.

## Example

You send the agent the following message:
```
Load Youtube
```
The agent will search for "Youtube" on google and load the website https://www.youtube.com.

## Installation

```bash
pip install -r requirements.txt
```
Create a .env file with the following variables:

```bash
OPENAI_API_KEY=your_openai_api_key
```

## How to run

```bash
python webpage_research.py
```
