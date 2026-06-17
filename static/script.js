document.addEventListener('DOMContentLoaded', () => {
    const articleText = document.getElementById('article');
    const imageInput = document.getElementById('image_input');
    const analyzeBtn = document.getElementById('analyze_btn');
    const resultSection = document.getElementById('result_section');
    const errorSection = document.getElementById('error_section');
    const errorText = document.getElementById('error_text');
    const historySection = document.getElementById('history_section');
    const historyList = document.getElementById('history_list');
    const clearHistoryBtn = document.getElementById('clear_history_btn');
    const exportBtn = document.getElementById('export_btn');
    const uploadArea = document.getElementById('upload_area');
    const uploadPlaceholder = document.getElementById('upload_placeholder');
    const uploadPreview = document.getElementById('upload_preview');
    const previewImage = document.getElementById('preview_image');
    const removeImageBtn = document.getElementById('remove_image_btn');

    let analysisHistory = JSON.parse(localStorage.getItem('kartikey_history') || '[]');
    let currentTab = 'text_tab';
    let uploadedImageFile = null;

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(currentTab).classList.add('active');
        });
    });

    analyzeBtn.addEventListener('click', analyzeArticle);

    articleText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            analyzeArticle();
        }
    });

    exportBtn.addEventListener('click', exportResults);

    clearHistoryBtn.addEventListener('click', () => {
        analysisHistory = [];
        localStorage.removeItem('kartikey_history');
        renderHistory();
    });

    uploadArea.addEventListener('click', () => imageInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleImageFile(files[0]);
        }
    });

    imageInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleImageFile(e.target.files[0]);
        }
    });

    removeImageBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearImageUpload();
    });

    function handleImageFile(file) {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            showError('Please upload a valid image (JPEG, PNG, GIF, or WebP).');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showError('Image is too large. Please upload an image under 10MB.');
            return;
        }

        uploadedImageFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            uploadPlaceholder.style.display = 'none';
            uploadPreview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }

    function clearImageUpload() {
        uploadedImageFile = null;
        imageInput.value = '';
        uploadPlaceholder.style.display = 'block';
        uploadPreview.style.display = 'none';
        previewImage.src = '';
    }

    renderHistory();

    function analyzeArticle() {
        resultSection.style.display = 'none';
        errorSection.style.display = 'none';

        if (currentTab === 'text_tab') {
            analyzeText();
        } else if (currentTab === 'image_tab') {
            analyzeImage();
        }
    }

    function analyzeText() {
        const article = articleText.value.trim();

        if (!article) {
            showError('Please paste an article to analyze.');
            articleText.focus();
            return;
        }
        if (article.length < 50) {
            showError('Article text is too short. Please enter at least 50 characters.');
            articleText.focus();
            return;
        }

        setLoading(true);
        fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article: article })
        })
            .then(r => {
                if (!r.ok) {
                    return r.json().then(err => { throw new Error(err.error || err.fetch_error || `Server error (${r.status})`); });
                }
                return r.json();
            })
            .then(data => {
                data.article_preview = article.substring(0, 80) + (article.length > 80 ? '...' : '');
                displayResults(data);
                addToHistory(data);
            })
            .catch(err => {
                showError(err.message || 'An unexpected error occurred.');
            })
            .finally(() => setLoading(false));
    }

    function analyzeImage() {
        if (!uploadedImageFile) {
            showError('Please upload an image to analyze.');
            return;
        }

        const formData = new FormData();
        formData.append('image', uploadedImageFile);

        setLoading(true, 'Analyzing image...');
        fetch('/analyze-image', {
            method: 'POST',
            body: formData
        })
            .then(r => {
                if (!r.ok) {
                    return r.json().then(err => { throw new Error(err.error || `Server error (${r.status})`); });
                }
                return r.json();
            })
            .then(data => {
                data.article_preview = `Image: ${uploadedImageFile.name}`;
                displayResults(data);
                addToHistory(data);
            })
            .catch(err => {
                showError(err.message || 'An unexpected error occurred.');
            })
            .finally(() => setLoading(false));
    }

    function setLoading(isLoading, message) {
        const btnText = analyzeBtn.querySelector('.btn-text');
        const btnLoader = analyzeBtn.querySelector('.btn-loader');
        if (isLoading) {
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline';
            if (message) btnLoader.textContent = '⏳ ' + message;
            else btnLoader.textContent = '⏳ Kartikey is analyzing...';
            analyzeBtn.disabled = true;
        } else {
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
            analyzeBtn.disabled = false;
        }
    }

    function displayResults(data) {
        // Verdict
        const verdictBadge = document.getElementById('verdict_badge');
        const verdictText = document.getElementById('verdict_text');

        verdictBadge.className = 'verdict-badge';
        const verdict = data.verdict || 'Cannot Verify';
        const verdictLower = verdict.toLowerCase().replace(/\s+/g, '-');

        if (verdictLower.includes('real')) verdictBadge.classList.add('real');
        else if (verdictLower.includes('fake')) verdictBadge.classList.add('fake');
        else if (verdictLower.includes('misleading')) verdictBadge.classList.add('misleading');
        else verdictBadge.classList.add('cannot-verify');

        verdictText.textContent = verdict;

        // Score
        const score = Math.min(100, Math.max(0, data.credibility_score || 0));
        const scoreValue = document.getElementById('score_value');
        const scoreFill = document.getElementById('score_fill');
        const circumference = 2 * Math.PI * 52;
        const offset = circumference - (score / 100) * circumference;

        scoreValue.textContent = '0';
        scoreFill.style.strokeDasharray = circumference;
        scoreFill.style.strokeDashoffset = circumference;
        scoreFill.style.stroke = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444';

        setTimeout(() => {
            scoreFill.style.strokeDashoffset = offset;
            animateNumber(scoreValue, score, 1000);
        }, 100);

        // Explanation
        document.getElementById('explanation_text').textContent = data.explanation || 'No explanation provided.';

        // Clickbait
        const clickbaitCard = document.getElementById('clickbait_card');
        const clickbaitIcon = document.getElementById('clickbait_icon');
        const clickbaitStatus = document.getElementById('clickbait_status');
        const clickbaitExplanation = document.getElementById('clickbait_explanation');

        clickbaitCard.className = 'feature-card clickbait-card';
        if (data.clickbait_detected) {
            clickbaitCard.classList.add('clickbait-yes');
            clickbaitIcon.textContent = '🚨';
            clickbaitStatus.className = 'clickbait-status clickbait-yes-text';
            clickbaitStatus.textContent = '⚠️ Clickbait Detected!';
            clickbaitExplanation.textContent = data.clickbait_explanation || 'This article uses clickbait techniques.';
        } else {
            clickbaitCard.classList.add('clickbait-no');
            clickbaitIcon.textContent = '✅';
            clickbaitStatus.className = 'clickbait-status clickbait-no-text';
            clickbaitStatus.textContent = '✓ No Clickbait Detected';
            clickbaitExplanation.textContent = data.clickbait_explanation || 'The headline matches the article content.';
        }

        // Tone
        const toneText = document.getElementById('tone_text');
        const toneBadge = document.getElementById('tone_badge');
        const toneIcon = document.getElementById('tone_icon');
        const tone = data.emotional_tone || 'Neutral';

        if (tone.toLowerCase().includes('sensational') || tone.toLowerCase().includes('fear') || tone.toLowerCase().includes('fear-mongering')) {
            toneIcon.textContent = '🔴';
            toneBadge.style.background = '#fee2e2';
            toneBadge.style.color = '#991b1b';
        } else if (tone.toLowerCase().includes('calm') || tone.toLowerCase().includes('neutral')) {
            toneIcon.textContent = '🟢';
            toneBadge.style.background = '#d1fae5';
            toneBadge.style.color = '#065f46';
        } else {
            toneIcon.textContent = '🟡';
            toneBadge.style.background = '#fef3c7';
            toneBadge.style.color = '#92400e';
        }
        toneText.textContent = tone;

        // Red Flags
        const redFlagsList = document.getElementById('red_flags_list');
        redFlagsList.innerHTML = '';
        if (data.red_flags && data.red_flags.length > 0) {
            data.red_flags.forEach(flag => {
                const li = document.createElement('li');
                li.textContent = flag;
                redFlagsList.appendChild(li);
            });
        } else {
            redFlagsList.innerHTML = '<li>No red flags identified.</li>';
        }

        // Trustworthy Elements
        const trustworthyList = document.getElementById('trustworthy_list');
        trustworthyList.innerHTML = '';
        if (data.trustworthy_elements && data.trustworthy_elements.length > 0) {
            data.trustworthy_elements.forEach(element => {
                const li = document.createElement('li');
                li.textContent = element;
                trustworthyList.appendChild(li);
            });
        } else {
            trustworthyList.innerHTML = '<li>No trustworthy elements identified.</li>';
        }

        // Tips
        const tipsList = document.getElementById('tips_list');
        tipsList.innerHTML = '';
        if (data.source_reliability_tips && data.source_reliability_tips.length > 0) {
            data.source_reliability_tips.forEach(tip => {
                const li = document.createElement('li');
                li.textContent = tip;
                tipsList.appendChild(li);
            });
        } else {
            tipsList.innerHTML = '<li>Cross-check this article with other reliable sources.</li>';
        }

        // Summary
        document.getElementById('summary_text').textContent = data.summary || 'No summary provided.';

        window._lastResult = data;

        resultSection.style.display = 'block';
        errorSection.style.display = 'none';
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function showError(message) {
        errorText.textContent = message;
        errorSection.style.display = 'block';
        resultSection.style.display = 'none';
        errorSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function animateNumber(element, target, duration) {
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            element.textContent = Math.round(start + (target - start) * eased);
            if (progress < 1) requestAnimationFrame(update);
            else element.textContent = target;
        }
        requestAnimationFrame(update);
    }

    function addToHistory(data) {
        const entry = {
            id: Date.now(),
            verdict: data.verdict || 'Cannot Verify',
            score: data.credibility_score || 0,
            preview: data.article_preview || 'Analysis',
            timestamp: new Date().toLocaleString()
        };

        analysisHistory.unshift(entry);
        if (analysisHistory.length > 10) analysisHistory = analysisHistory.slice(0, 10);
        localStorage.setItem('kartikey_history', JSON.stringify(analysisHistory));
        renderHistory();
    }

    function renderHistory() {
        historyList.innerHTML = '';
        if (analysisHistory.length === 0) {
            historySection.style.display = 'none';
            return;
        }
        historySection.style.display = 'block';

        analysisHistory.forEach(entry => {
            const item = document.createElement('div');
            item.className = 'history-item';

            const verdictClass = entry.verdict.toLowerCase().replace(/\s+/g, '-');

            const timeSpan = document.createElement('span');
            timeSpan.style.fontSize = '0.7rem';
            timeSpan.style.color = '#9ca3af';
            timeSpan.style.marginRight = '8px';
            timeSpan.textContent = entry.timestamp;

            const verdictSpan = document.createElement('span');
            verdictSpan.className = `history-verdict ${verdictClass}`;
            verdictSpan.textContent = entry.verdict;

            const previewSpan = document.createElement('span');
            previewSpan.className = 'history-preview';
            previewSpan.textContent = entry.preview;

            const scoreSpan = document.createElement('span');
            scoreSpan.className = 'history-score';
            scoreSpan.textContent = entry.score + '%';

            item.append(timeSpan, verdictSpan, previewSpan, scoreSpan);
            item.addEventListener('click', () => articleText.focus());
            historyList.appendChild(item);
        });
    }

    function exportResults() {
        const data = window._lastResult;
        if (!data) return;

        const lines = [
            '═══════════════════════════════════════',
            '  Kartikey - Fake News Analysis Report',
            '═══════════════════════════════════════',
            '',
            `Verdict: ${data.verdict || 'N/A'}`,
            `Credibility Score: ${data.credibility_score || 0}/100`,
            '',
            `Explanation: ${data.explanation || 'N/A'}`,
            '',
            `Clickbait Detected: ${data.clickbait_detected ? 'Yes ⚠️' : 'No ✓'}`,
            data.clickbait_explanation ? `Clickbait Details: ${data.clickbait_explanation}` : '',
            `Emotional Tone: ${data.emotional_tone || 'Neutral'}`,
            '',
            'Red Flags:',
            ...(data.red_flags && data.red_flags.length > 0
                ? data.red_flags.map(f => `  • ${f}`)
                : ['  • None identified']),
            '',
            'Trustworthy Elements:',
            ...(data.trustworthy_elements && data.trustworthy_elements.length > 0
                ? data.trustworthy_elements.map(e => `  ✓ ${e}`)
                : ['  • None identified']),
            '',
            'Verification Tips:',
            ...(data.source_reliability_tips && data.source_reliability_tips.length > 0
                ? data.source_reliability_tips.map(t => `  💡 ${t}`)
                : ['  • Cross-check with reliable sources']),
            '',
            `Summary: ${data.summary || 'N/A'}`,
            '',
            '───────────────────────────────────────',
            'Generated by Kartikey Fake News Detector',
            'Powered by OpenAI'
        ];

        const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `kartikey-analysis-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
});