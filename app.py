import os
import re
import json
import io
import base64
from flask import Flask, render_template, request, jsonify
from google import genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from PIL import Image

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def clean_text(text):
    """Remove excessive whitespace and normalize text."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_article_from_url(url):
    """Fetch and extract article text from a URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, nav, footer, header elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Extract text from common article containers
        article_text = ""
        
        # Try article tag first
        article_tag = soup.find('article')
        if article_tag:
            article_text = article_tag.get_text(separator='\n', strip=True)
        
        # Fallback to main content
        if len(article_text) < 100:
            main_tag = soup.find('main') or soup.find('div', class_=re.compile(r'content|article|post|entry', re.I))
            if main_tag:
                article_text = main_tag.get_text(separator='\n', strip=True)
        
        # Last fallback: get all paragraph text
        if len(article_text) < 100:
            paragraphs = soup.find_all('p')
            article_text = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        
        if not article_text or len(article_text) < 50:
            return None, "Could not extract enough meaningful text from this URL."
        
        return clean_text(article_text), None
    except requests.exceptions.Timeout:
        return None, "Request timed out. The website took too long to respond."
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP error {e.response.status_code} when accessing the URL."
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to the website. Please check the URL."
    except Exception as e:
        return None, f"Failed to fetch article: {str(e)[:100]}"

def analyze_image_with_gemini(image_data, api_key):
    """Analyze a news screenshot image using Gemini vision."""
    client = genai.Client(api_key=api_key)
    
    prompt = """You are Kartikey, a friendly fact-checking AI assistant for students. 
This image is a screenshot or photo of a news article, social media post, or headline. 
Analyze its credibility and provide a structured response in JSON format (no markdown, no code blocks):

{
    "credibility_score": <number between 0 and 100>,
    "verdict": "<Real News / Fake News / Misleading / Cannot Verify>",
    "explanation": "<brief 2-3 sentence explanation of the verdict>",
    "red_flags": ["<list any red flags or suspicious elements found>"],
    "trustworthy_elements": ["<list any trustworthy elements found>"],
    "clickbait_detected": <true/false>,
    "clickbait_explanation": "<if clickbait detected, explain why; otherwise empty string>",
    "emotional_tone": "<Calm / Sensational / Neutral / Fear-mongering / Celebratory>",
    "source_reliability_tips": ["<list 2-3 tips on how to verify this content>"],
    "summary": "<a concise 2-3 sentence summary of what the image shows>"
}"""
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-lite',
        contents=[prompt, image_data]
    )
    return response

def analyze_text_with_gemini(article_text, api_key):
    """Send article text to Gemini and get credibility analysis."""
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are Kartikey, a friendly fact-checking AI assistant designed to help students detect fake news. Analyze the following article and provide a structured response in JSON format (no markdown, no code blocks):

{{
    "credibility_score": <number between 0 and 100>,
    "verdict": "<Real News / Fake News / Misleading / Cannot Verify>",
    "explanation": "<brief 2-3 sentence explanation of the verdict>",
    "red_flags": ["<list any red flags or suspicious elements found>"],
    "trustworthy_elements": ["<list any trustworthy elements found>"],
    "clickbait_detected": <true/false>,
    "clickbait_explanation": "<if clickbait detected, explain why; otherwise empty string>",
    "emotional_tone": "<Calm / Sensational / Neutral / Fear-mongering / Celebratory>",
    "source_reliability_tips": ["<list 2-3 tips on how to verify this article's claims>"],
    "summary": "<a concise 2-3 sentence summary of the article>"
}}

Article to analyze:
{article_text}
"""
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-lite',
        contents=prompt
    )
    return response

def parse_gemini_response(raw):
    """Parse Gemini response to extract JSON."""
    raw = raw.strip()
    # Remove markdown code block markers if present
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = None
        else:
            result = None
    
    if result is None:
        result = {
            "credibility_score": 50,
            "verdict": "Cannot Verify",
            "explanation": "Unable to parse the analysis response properly.",
            "red_flags": [],
            "trustworthy_elements": [],
            "clickbait_detected": False,
            "clickbait_explanation": "",
            "emotional_tone": "Neutral",
            "source_reliability_tips": [],
            "summary": "Analysis could not be completed."
        }
    
    return result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    article_text = data.get('article', '').strip()
    api_key = data.get('api_key', '').strip()
    
    if not article_text:
        return jsonify({'error': 'Please enter an article text to analyze.'}), 400
    if not api_key:
        return jsonify({'error': 'Please provide your Gemini API key.'}), 400
    if len(article_text) < 50:
        return jsonify({'error': 'Article text is too short. Please enter at least 50 characters.'}), 400
    
    try:
        article_text = clean_text(article_text)
        response = analyze_text_with_gemini(article_text, api_key)
        result = parse_gemini_response(response.text)
        return jsonify(result)
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg or "403" in error_msg or "INVALID_ARGUMENT" in error_msg:
            return jsonify({'error': 'Invalid Gemini API key. Please check your key and try again.'}), 400
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return jsonify({'error': 'Gemini API rate limit exceeded. Please wait and try again.'}), 429
        return jsonify({'error': f'Analysis failed: {error_msg[:200]}'}), 500

@app.route('/analyze-url', methods=['POST'])
def analyze_url():
    data = request.get_json()
    url = data.get('url', '').strip()
    api_key = data.get('api_key', '').strip()
    
    if not url:
        return jsonify({'error': 'Please enter a URL to analyze.'}), 400
    if not api_key:
        return jsonify({'error': 'Please provide your Gemini API key.'}), 400
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # Fetch article from URL
        article_text, fetch_error = fetch_article_from_url(url)
        
        if fetch_error:
            return jsonify({'error': fetch_error}), 400
        
        if not article_text or len(article_text) < 50:
            return jsonify({'error': 'Could not extract enough text from this URL. The page may require JavaScript or be behind a login.'}), 400
        
        # Analyze the extracted text
        response = analyze_text_with_gemini(article_text, api_key)
        result = parse_gemini_response(response.text)
        
        # Add source info
        result['source_url'] = url
        result['article_preview'] = article_text[:80] + '...' if len(article_text) > 80 else article_text
        
        return jsonify(result)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return jsonify({'error': 'Gemini API rate limit exceeded. Please wait and try again.'}), 429
        return jsonify({'error': f'Analysis failed: {error_msg[:200]}'}), 500

@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    api_key = request.form.get('api_key', '').strip()
    
    if not api_key:
        return jsonify({'error': 'Please provide your Gemini API key.'}), 400
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded. Please select an image.'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected.'}), 400
    
    # Validate file type
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    if file.content_type not in allowed_types:
        return jsonify({'error': 'Please upload a valid image (JPEG, PNG, GIF, or WebP).'}), 400
    
    try:
        image_bytes = file.read()
        
        if len(image_bytes) > 10 * 1024 * 1024:
            return jsonify({'error': 'Image is too large. Please upload an image under 10MB.'}), 400
        
        img = Image.open(io.BytesIO(image_bytes))
        response = analyze_image_with_gemini(img, api_key)
        result = parse_gemini_response(response.text)
        
        return jsonify(result)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return jsonify({'error': 'Gemini API rate limit exceeded. Please wait and try again.'}), 429
        return jsonify({'error': f'Image analysis failed: {error_msg[:200]}'}), 500

if __name__ == '__main__':
    app.run(debug=True)