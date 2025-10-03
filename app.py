from flask import Flask, render_template, jsonify, request
import os
import random
import json
import requests
from dotenv import load_dotenv, find_dotenv
from supabase import create_client, Client

# Load .env if present so GROQ_API_KEY or GROQ_DEFAULT_MODEL can be set
env = find_dotenv()
if env:
    load_dotenv(env)

app = Flask(__name__)

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/question-generator')
def question_generator():
    return render_template('question_generator.html')

@app.route('/flashcards')
def flashcards():
    return render_template('flashcards.html')

@app.route('/review')
def review():
    return render_template('review.html')

@app.route('/api/health')
def health():
    return jsonify({'service': 'Brain Bee', 'status': 'ok'})


@app.route('/api/categories')
def categories():
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    cats = []
    if os.path.isdir(data_dir):
        for fn in os.listdir(data_dir):
            if fn.lower().endswith('.txt'):
                cats.append(fn[:-4])
    return jsonify({'categories': sorted(cats)})


def _read_random_chunk(filepath, size=10000):
    # Read file bytes then pick a random window of approximately `size` chars
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    if len(text) <= size:
        return text
    start = random.randint(0, max(0, len(text) - size))
    return text[start:start+size]

def evaluate_question_quality(question_data, original_chunk):
    """Evaluate the quality of the generated question using Groq"""
    
    evaluation_prompt = f"""
    Evaluate this multiple-choice question for quality and educational value. Rate it on a scale of 1-10.
    
    ORIGINAL PASSAGE CONTEXT:
    {original_chunk[:2000]}
    
    GENERATED QUESTION:
    {question_data['question']}
    
    ANSWER CHOICES:
    {chr(10).join([f"{i+1}. {choice}" for i, choice in enumerate(question_data['choices'])])}
    
    CORRECT ANSWER: Choice {question_data['answer'] + 1}
    RATIONALE: {question_data.get('rationale', 'No rationale provided')}
    
    Evaluation Criteria:
    1. Relevance to passage (1-3 points)
    2. Clarity and specificity (1-3 points) 
    3. Quality of distractors (1-2 points)
    4. Appropriate difficulty (1-2 points)
    
    Respond with ONLY a JSON object in this format:
    {{
        "quality_score": <number 1-10>,
        "quality_feedback": "<brief explanation of rating>"
    }}
    """
    
    try:
        # Use requests instead of openai library to avoid conflicts
        api_key = os.getenv('GROQ_API_KEY')
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'llama-3.1-8b-instant',
            'messages': [
                {"role": "system", "content": "You are an expert educational content evaluator. Be strict but fair in your assessments."},
                {"role": "user", "content": evaluation_prompt}
            ],
            'temperature': 0.1,
            'max_tokens': 200
        }
        
        resp = requests.post('https://api.groq.com/openai/v1/chat/completions', json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            eval_text = data['choices'][0]['message']['content']
            
            # Parse JSON from response
            start = eval_text.find('{')
            end = eval_text.rfind('}')
            if start != -1 and end != -1:
                eval_data = json.loads(eval_text[start:end+1])
                return eval_data.get('quality_score', 5), eval_data.get('quality_feedback', 'No feedback provided')
    except Exception as e:
        print(f"Quality evaluation failed: {e}")
    
    return 5, "Automatic evaluation failed"

def store_question_in_supabase(question_data, category, difficulty, quality_score, quality_feedback):
    """Store the question in Supabase database"""
    try:
        data = {
            'category': category,
            'question_text': question_data['question'],
            'choices': question_data['choices'],
            'correct_answer': question_data['answer'],  # This is the integer index
            'difficulty': difficulty,
            'quality_score': quality_score,
            'quality_feedback': quality_feedback,
            'rationale': question_data.get('rationale'),
            'source_span': question_data.get('source_span')
        }
        
        result = supabase.table('questions').insert(data).execute()
        return True
    except Exception as e:
        print(f"Failed to store question in Supabase: {e}")
        return False

@app.route('/api/generate-question', methods=['POST'])
def generate_question():
    body = request.get_json() or {}
    category = body.get('category')
    difficulty = body.get('difficulty', 'medium')
    if difficulty not in ('easy','medium','hard'):
        difficulty = 'medium'
    model = os.getenv('GROQ_DEFAULT_MODEL') or 'llama-3.1-8b-instant'

    if not category:
        return jsonify({'error': 'category required'}), 400

    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    filename = os.path.join(data_dir, category + '.txt')
    if not os.path.isfile(filename):
        return jsonify({'error': 'category not found'}), 404

    chunk = _read_random_chunk(filename, size=10000)

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return jsonify({'error': 'GROQ_API_KEY not configured on server. Cannot call model.'}), 500

    # USE YOUR EXACT WORKING PROMPT - DON'T CHANGE IT
    diff_hint = {
        'easy': 'Use simpler vocabulary, shorter sentences, and include an obvious clue in the passage-based question. Focus on basic comprehension and recognition.',
        'medium': 'Use age-appropriate vocabulary, modest multi-step reasoning, and plausible distractors.',
        'hard': 'Use more challenging reasoning, multi-step inference, and slightly denser language appropriate for upper-grade students.'
    }[difficulty]

    # USE YOUR EXACT WORKING SYSTEM PROMPT
    system = (
        "You are an expert children's science educator and question-writer. Your job is to read a provided passage and create ONE detailed, scenario-based multiple-choice question (Brain Bee style) that tests comprehension and reasoning about the passage."
        " Use clear, kid-appropriate language, include a short context sentence that sets up a hypothetical scenario based on the passage, and then ask the question."
        " Provide exactly FOUR plausible answer choices where distractors are believable but only one choice is supported by the passage."
        " STRICTLY reply with a single JSON object and nothing else. The JSON must include these keys:"
        " question: string (the full question including the scenario sentence),"
        " choices: array of 4 strings,"
        " answer: integer index (0-3) indicating the correct choice,"
        " rationale: a short plain-language sentence (1-2 sentences) explaining why the correct answer is correct and why the others are not,"
        " source_span: optional short excerpt (up to 200 chars) copied verbatim from the provided passage that supports the correct answer."
    )

    # USE YOUR EXACT WORKING USER PROMPT
    user = (
        "You will be given a passage delimited by triple backticks. BASE YOUR QUESTION ONLY ON THE INFORMATION IN THE PASSAGE. Do not add facts beyond it.\n\n""" )
    user += chunk + "\n```\n\nRespond with the JSON object described above. Do not include commentary, prefaces, or markdown — only the JSON object."

    # also append a short instruction about difficulty
    user += "\n\nDifficulty guidance: " + diff_hint

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user}
        ],
        'temperature': 0.7,
        'max_tokens': 400,
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.post('https://api.groq.com/openai/v1/chat/completions', json=payload, headers=headers, timeout=30)
    except Exception as e:
        return jsonify({'error': f'Network error: {e}'}), 502

    if resp.status_code != 200:
        return jsonify({'error': f'Upstream error {resp.status_code}', 'detail': resp.text}), resp.status_code

    text = ''
    try:
        data = resp.json()
        # try to extract assistant text
        text = data['choices'][0]['message']['content']
    except Exception:
        return jsonify({'error': 'Bad response from model', 'raw': resp.text}), 502

    # Try to parse JSON from model output
    parsed = None
    try:
        # Find first { ... } in text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            j = text[start:end+1]
            parsed = json.loads(j)
    except Exception:
        parsed = None

    if not parsed:
        return jsonify({'error': 'Could not parse JSON from model output', 'raw': text}), 502

    # USE YOUR EXACT WORKING VALIDATION
    q = parsed.get('question')
    choices = parsed.get('choices')
    answer = parsed.get('answer')
    if not q or not isinstance(choices, list) or len(choices) != 4 or not isinstance(answer, int):
        return jsonify({'error': 'Model returned invalid structure', 'parsed': parsed}), 502

    # Clean choices - remove any prefix letters if the model still included them
    cleaned_choices = []
    for choice in choices:
        # Remove common prefixes like "A)", "B.", "C) ", etc.
        cleaned = choice.strip()
        if len(cleaned) > 2 and cleaned[1] in [')', '.', ':']:
            cleaned = cleaned[2:].strip()
        elif len(cleaned) > 3 and cleaned[2] in [')', '.', ':']:
            cleaned = cleaned[3:].strip()
        cleaned_choices.append(cleaned)

    # RANDOMIZE THE CHOICE ORDER IN PYTHON
    indices = list(range(4))
    random.shuffle(indices)
    
    shuffled_choices = [cleaned_choices[i] for i in indices]
    
    # Find the new position of the correct answer after shuffling
    new_correct_index = indices.index(answer)

    # Prepare question data
    question_data = {
        'question': q,
        'choices': shuffled_choices,
        'answer': new_correct_index,
        'rationale': parsed.get('rationale'),
        'source_span': parsed.get('source_span')
    }

    # Evaluate question quality (this happens after we get valid data)
    quality_score, quality_feedback = evaluate_question_quality(question_data, chunk)

    # Store in Supabase (this happens after we get valid data)
    store_success = store_question_in_supabase(
        question_data, category, difficulty, quality_score, quality_feedback
    )

    # Return the structured question with quality info
    return jsonify({
        'question': q, 
        'choices': shuffled_choices, 
        'answer': new_correct_index, 
        'rationale': parsed.get('rationale'), 
        'source_span': parsed.get('source_span'), 
        'quality_score': quality_score,
        'quality_feedback': quality_feedback,
        'stored_in_db': store_success,
        'raw_model': text
    })

@app.route('/api/check-answer', methods=['POST'])
def check_answer():
    """Simple server-side check of a user's selected index against the expected answer."""
    body = request.get_json() or {}
    expected = body.get('answer')
    selected = body.get('selected')
    rationale = body.get('rationale')
    source_span = body.get('source_span')

    if expected is None or selected is None:
        return jsonify({'error': 'expected (answer) and selected required'}), 400

    try:
        expected_i = int(expected)
        selected_i = int(selected)
    except Exception:
        return jsonify({'error': 'answer and selected must be integers'}), 400

    is_correct = (expected_i == selected_i)
    return jsonify({'is_correct': is_correct, 'expected': expected_i, 'selected': selected_i, 'rationale': rationale, 'source_span': source_span})

# New endpoint to get question statistics
@app.route('/api/question-stats', methods=['GET'])
def question_stats():
    """Get statistics about stored questions"""
    try:
        # Count questions by category and difficulty
        result = supabase.table('questions').select('category, difficulty, quality_score').execute()
        questions = result.data
        
        stats = {}
        for q in questions:
            cat = q['category']
            if cat not in stats:
                stats[cat] = {'total': 0, 'by_difficulty': {}, 'avg_quality': 0}
            
            stats[cat]['total'] += 1
            stats[cat]['by_difficulty'][q['difficulty']] = stats[cat]['by_difficulty'].get(q['difficulty'], 0) + 1
        
        # Calculate average quality scores
        for cat in stats:
            cat_questions = [q for q in questions if q['category'] == cat and q['quality_score']]
            if cat_questions:
                stats[cat]['avg_quality'] = sum(q['quality_score'] for q in cat_questions) / len(cat_questions)
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Failed to get stats: {e}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)