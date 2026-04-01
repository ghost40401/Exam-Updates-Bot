# Exam Updates Bot

This is a personal automation tool designed to track official announcements for NEET UG, JEE Main, and ICAI exams. Instead of manually checking multiple government portals every day, this script monitors them automatically and sends a notification to my Discord server.

### How it Works
The bot is written in Python and uses Playwright to scrape the circulars and notices sections of the official websites. It runs on a schedule using GitHub Actions. To avoid getting the same notification multiple times, it stores the links it has already processed in a file called posted.json.

### Sites Tracked
The bot monitors all circulars, notices, and notifications (including exam dates, registration windows, admit card releases, and results) across the following portals:
* NTA NEET UG
* NTA JEE Main
* ICAI (BOS, Foundation, Intermediate, and Final)

### Preview
![Exam Updates Bot in action](https://github.com/user-attachments/assets/2f89721b-d99b-4178-8d6f-5953017b0d02)
