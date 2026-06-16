# Kartikey - Fake News Detector for Students

An AI-powered web application that helps students detect fake news by analyzing article text, URLs, or images using Google Gemini AI.

## Features

- **Paste Text Analysis** — Paste any article text and get a credibility analysis
- **URL Analysis** — Enter a news article URL; Kartikey fetches and analyzes the content
- **Image Analysis** — Upload screenshots or photos of news articles for visual analysis
- **Credibility Scoring** — Numeric score (0-100) with visual ring indicator
- **Verdict Classification** — Real News, Fake News, Misleading, or Cannot Verify
- **Clickbait Detection** — Identifies sensationalist headlines and clickbait techniques
- **Emotional Tone Analysis** — Detects emotional manipulation (fear-mongering, sensationalism, etc.)
- **Red Flag Detection** — Lists suspicious elements found in the article
- **Trustworthy Elements** — Highlights credible aspects of the content
- **Verification Tips** — Actionable tips on how to verify the article claims
- **Analysis History** — Stores last 10 analyses locally in browser
- **Export Reports** — Export analysis results as a text file
- **Drag and Drop Images** — Easy image upload with drag-and-drop support

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python / Flask |
| Frontend | HTML, CSS, JavaScript |
| AI API | Google Gemini (gemini-2.0-flash-lite) |
| Web Scraping | BeautifulSoup4 / Requests |
| Image Processing | Pillow (PIL) |

## Project Structure

```
Fake-News-Detector-for-Students/
├── app.py                 # Flask application with API routes
├── requirements.txt       # Python dependencies
├── static/
│   ├── script.js          # Frontend JavaScript logic
│   └── style.css          # Application styles
├── templates/
│   └── index.html         # Main HTML template
└── README.md              # This file
```

## Prerequisites

- Python 3.8+
- A Google Gemini API key (get one at [Google AI Studio](https://aistudio.google.com/apikey))

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Kartikey0907/Fake-News-Detector-for-Students.git
   cd Fake-News-Detector-for-Students
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the application**
   ```bash
   python app.py
   ```

2. **Open your browser** to `http://127.0.0.1:5000`

3. **Enter your Gemini API key** in the API Key field at the top

4. **Choose an input method**:
   - **Paste Text** — Paste an article (min 50 characters) and click Analyze
   - **URL** — Enter a news article URL to fetch and analyze
   - **Image** — Upload a screenshot or photo of a news article

5. **Review the results**: credibility score, verdict, red flags, clickbait analysis, emotional tone, and verification tips

## API Endpoints

### POST /analyze
Analyze article text.

**Request body:**
```json
{
  "article": "Full article text here...",
  "api_key": "your-gemini-api-key"
}
```

### POST /analyze-url
Fetch and analyze article from a URL.

**Request body:**
```json
{
  "url": "https://example.com/news-article",
  "api_key": "your-gemini-api-key"
}
```

### POST /analyze-image
Analyze a news screenshot image.

**Form data:**
- `api_key` — Your Gemini API key
- `image` — Image file (JPEG, PNG, GIF, or WebP, max 10MB)

### GET /
Render the main application page.

## Response Format

All analysis endpoints return a JSON object:

```json
{
  "credibility_score": 72,
  "verdict": "Real News",
  "explanation": "The article is well-sourced with quotes from verified experts...",
  "red_flags": ["Uses vague unnamed sources"],
  "trustworthy_elements": ["Multiple primary sources cited"],
  "clickbait_detected": false,
  "clickbait_explanation": "",
  "emotional_tone": "Calm",
  "source_reliability_tips": [
    "Cross-check with other reputable news sources",
    "Verify the author's credentials"
  ],
  "summary": "The article reports on recent policy changes..."
}
```

## Limitations

- A Google Gemini API key is mandatory for analysis
- Some websites may block scraping or require JavaScript rendering
- AI-based analysis is not 100% accurate; always cross-check with multiple sources
- Minimum 50 characters required for text analysis
- Maximum 10MB for image uploads

## Disclaimer

This tool is for educational purposes. Always cross-check information with multiple reliable sources before drawing conclusions.

---

Built with ❤️ for students | Powered by Google Gemini AI