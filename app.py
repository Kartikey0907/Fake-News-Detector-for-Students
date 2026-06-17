import os
import re
import json
import io
import base64
import time
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- OpenAI Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"  # Good balance of speed/cost. Supports json response format.

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Rate Limit Retry Configuration ---
MAX_RETRIES = 8
INITIAL_BACKOFF = 5  # seconds (higher for free tier)
MAX_BACKOFF = 120     # seconds

def call_openai_with_retry(messages, max_retries=MAX_RETRIES, model=OPENAI_MODEL):
    """Call OpenAI API with exponential backoff retry logic for rate limit errors."""
    if not OPENAI_API_KEY or OPENAI_API_KEY == "sk-your-openai-api-key-here":
        raise ValueError("OpenAI API key is not configured. Please add it to the .env file.")
    
    # Only use response_format for models that support it
    kwargs = {"model": model, "messages": messages}
    if model in ("gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4-1106-preview", "gpt-3.5-turbo-1106"):
        kwargs["response_format"] = {"type": "json_object"}
    
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            last_error = e
            
            # Handle various error types
            if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                if attempt < max_retries - 1:
                    backoff = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                    jitter = backoff * 0.2 * (2 * random.random() - 1)
                    sleep_time = backoff + jitter
                    print(f"Rate limited. Retrying in {sleep_time:.1f} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    raise
            else:
                raise
    
    raise last_error


def encode_image_to_base64(image_path_or_bytes):
    """Convert an image to base64 for OpenAI vision API."""
    if isinstance(image_path_or_bytes, bytes):
        return base64.b64encode(image_path_or_bytes).decode('utf-8')
    elif isinstance(image_path_or_bytes, str):
        with open(image_path_or_bytes, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    else:
        buffer = io.BytesIO()
        image_path_or_bytes.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')


def clean_text(text):
    """Remove excessive whitespace and normalize text."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def analyze_text_with_openai(article_text):
    """Send article text to OpenAI and get credibility analysis."""
    system_prompt = """You are Kartikey, a friendly fact-checking AI assistant for students. Your job is to evaluate article credibility based on the content provided.

IMPORTANT RULES:
1. If the article reads like legitimate, factual, well-sourced news reporting with no obvious bias or misinformation — label it "Real News" with a score of 70-100.
2. "Cannot Verify" should ONLY be used when the article is too short, too vague, or lacks enough content to make ANY assessment. When using "Cannot Verify", the credibility_score MUST be 50 (neutral/unknown).
3. If the article has signs of misinformation, bias, or lack of sources — use "Fake News" or "Misleading".
4. Always provide meaningful explanations, red flags, and trustworthy elements based on what you actually see in the text.
5. Legitimate news articles should be recognized as such — do not default to "Cannot Verify" for real news.

Respond ONLY with a valid JSON object (no markdown, no code blocks)."""

    user_prompt = f"""Analyze the following article for credibility and provide a structured response in JSON format with these fields:
{{
    "credibility_score": <number between 0 and 100>,
    "verdict": "<Real News / Fake News / Misleading / Cannot Verify>",
    "explanation": "<brief 2-3 sentence explanation of the verdict>",
    "red_flags": ["<list any red flags or suspicious elements found>"],
    "trustworthy_elements": ["<list any trustworthy elements found (e.g., factual tone, specific details, neutral language, citations, quotes from officials, etc.)>"],
    "clickbait_detected": <true/false>,
    "clickbait_explanation": "<if clickbait detected, explain why; otherwise empty string>",
    "emotional_tone": "<Calm / Sensational / Neutral / Fear-mongering / Celebratory>",
    "source_reliability_tips": ["<list 2-3 tips on how to verify this article's claims>"],
    "summary": "<a concise 2-3 sentence summary of the article>"
}}

Article to analyze:
{article_text}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    result_text = call_openai_with_retry(messages)
    return result_text


def analyze_image_with_openai(image_data):
    """Analyze a news screenshot image using OpenAI vision."""
    base64_image = encode_image_to_base64(image_data)
    
    system_prompt = """You are Kartikey, a friendly fact-checking AI assistant for students. 
Analyze the image (a news screenshot, social media post, or headline) for credibility.

IMPORTANT RULES:
1. If the content in the image looks like legitimate, factual news with no obvious signs of misinformation — label it "Real News" with a score of 70-100.
2. "Cannot Verify" should ONLY be used when the image content is too vague, blurry, or lacks enough text to make ANY assessment. When using "Cannot Verify", the credibility_score MUST be 50 (neutral/unknown).
3. If the headline/content has signs of misinformation, clickbait, or sensationalism — use "Fake News" or "Misleading".
4. Always provide meaningful trustworthy elements when you identify legitimate content.

Respond ONLY with a valid JSON object (no markdown, no code blocks)."""

    user_prompt = """Analyze this news image and provide a structured response in JSON format with these fields:
{
    "credibility_score": <number between 0 and 100>,
    "verdict": "<Real News / Fake News / Misleading / Cannot Verify>",
    "explanation": "<brief 2-3 sentence explanation of the verdict>",
    "red_flags": ["<list any red flags or suspicious elements found>"],
    "trustworthy_elements": ["<list any trustworthy elements found (e.g., factual tone, specific details, neutral language, reputable source visible)>"],
    "clickbait_detected": <true/false>,
    "clickbait_explanation": "<if clickbait detected, explain why; otherwise empty string>",
    "emotional_tone": "<Calm / Sensational / Neutral / Fear-mongering / Celebratory>",
    "source_reliability_tips": ["<list 2-3 tips on how to verify this content>"],
    "summary": "<a concise 2-3 sentence summary of what the image shows>"
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "low"
                    }
                }
            ]
        }
    ]
    
    result_text = call_openai_with_retry(messages)
    return result_text


def parse_openai_response(raw):
    """Parse OpenAI response to extract JSON."""
    raw = raw.strip()
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
    
    return post_process_result(result)


def post_process_result(result):
    """Fix logical inconsistencies in the AI response."""
    if not isinstance(result, dict):
        return result
    
    verdict = str(result.get("verdict", "Cannot Verify"))
    
    # Fix 1: "Cannot Verify" should have score 50 (neutral/unknown), not 0
    if verdict.lower() == "cannot verify":
        score = result.get("credibility_score", 0)
        if score is None or score < 40 or score > 60:
            result["credibility_score"] = 50
    
    # Fix 2: Fill empty explanation for "Cannot Verify"
    if verdict.lower() == "cannot verify" and (not result.get("explanation") or "No explanation" in str(result.get("explanation", ""))):
        result["explanation"] = "The available content does not provide enough information to determine credibility with certainty. Cross-check with reliable sources for verification."
    
    # Fix 3: "Real News" should have appropriate score
    if verdict.lower() in ("real news", "real"):
        score = result.get("credibility_score", 0)
        if score is None or score < 50:
            result["credibility_score"] = max(70, score if score else 70)
        result["verdict"] = "Real News"
    
    # Fix 4: "Fake News" should have appropriate score
    if verdict.lower() in ("fake news", "fake"):
        score = result.get("credibility_score", 0)
        if score is None or score > 50:
            result["credibility_score"] = min(30, score if score else 30)
        result["verdict"] = "Fake News"
    
    # Fix 5: Ensure score is a valid number 0-100
    score = result.get("credibility_score")
    if score is None or not isinstance(score, (int, float)):
        result["credibility_score"] = 50
    else:
        result["credibility_score"] = max(0, min(100, int(round(score))))
    
    # Fix 6: Ensure required fields exist
    if "explanation" not in result or not result.get("explanation"):
        result["explanation"] = "No explanation provided."
    if "red_flags" not in result or not isinstance(result.get("red_flags"), list):
        result["red_flags"] = []
    if "trustworthy_elements" not in result or not isinstance(result.get("trustworthy_elements"), list):
        result["trustworthy_elements"] = []
    if "source_reliability_tips" not in result or not isinstance(result.get("source_reliability_tips"), list):
        result["source_reliability_tips"] = ["Cross-check this article with other reliable sources."]
    
    return result


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    article_text = data.get('article', '').strip()
    
    if not article_text:
        return jsonify({'error': 'Please enter an article text to analyze.'}), 400
    if len(article_text) < 50:
        return jsonify({'error': 'Article text is too short. Please enter at least 50 characters.'}), 400
    
    try:
        article_text = clean_text(article_text)
        result_text = analyze_text_with_openai(article_text)
        result = parse_openai_response(result_text)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
            return jsonify({'error': 'Invalid OpenAI API key. Please update it in the .env file.'}), 400
        if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
            return jsonify({'error': 'OpenAI API rate limit exceeded. Please wait a minute and try again.'}), 429
        if "insufficient_quota" in error_msg.lower():
            return jsonify({'error': 'OpenAI API quota exceeded. Please check your billing plan.'}), 400
        if "safety" in error_msg.lower() or "content_filter" in error_msg.lower() or "blocked" in error_msg.lower():
            return jsonify({'error': 'Content was blocked by safety filters. Please try different content.'}), 400
        return jsonify({'error': f'Analysis failed: {error_msg[:200]}'}), 500


@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded. Please select an image.'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected.'}), 400
    
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    if file.content_type not in allowed_types:
        return jsonify({'error': 'Please upload a valid image (JPEG, PNG, GIF, or WebP).'}), 400
    
    try:
        image_bytes = file.read()
        
        if len(image_bytes) > 10 * 1024 * 1024:
            return jsonify({'error': 'Image is too large. Please upload an image under 10MB.'}), 400
        
        img = Image.open(io.BytesIO(image_bytes))
        # Need to use gpt-4o-mini for vision/image analysis
        global OPENAI_MODEL
        original_model = OPENAI_MODEL
        OPENAI_MODEL = "gpt-4o-mini"  # Vision requires gpt-4 models
        result_text = analyze_image_with_openai(img)
        OPENAI_MODEL = original_model
        result = parse_openai_response(result_text)
        
        return jsonify(result)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
            return jsonify({'error': 'OpenAI API rate limit exceeded. Please wait a minute and try again.'}), 429
        return jsonify({'error': f'Image analysis failed: {error_msg[:200]}'}), 500


if __name__ == '__main__':
    app.run(debug=True)