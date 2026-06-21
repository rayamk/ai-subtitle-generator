document.addEventListener('DOMContentLoaded', function() {
    const videoInput = document.getElementById('videoInput');
    const generateBtn = document.getElementById('generateBtn');
    const subtitlePreview = document.getElementById('subtitlePreview');
    const downloadBtn = document.getElementById('downloadBtn');
    const sourceLang = document.getElementById('sourceLang');
    const targetLang = document.getElementById('targetLang');
    const dropZone = document.getElementById('dropZone');

    let currentSrt = '';

    // Click to upload
    dropZone.addEventListener('click', function() {
        videoInput.click();
    });

    // Drag and drop
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.style.borderColor = '#667eea';
        dropZone.style.background = 'rgba(102,126,234,0.08)';
    });

    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        dropZone.style.borderColor = 'rgba(255,255,255,0.15)';
        dropZone.style.background = 'rgba(255,255,255,0.03)';
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.style.borderColor = 'rgba(255,255,255,0.15)';
        dropZone.style.background = 'rgba(255,255,255,0.03)';
        if (e.dataTransfer.files.length > 0) {
            videoInput.files = e.dataTransfer.files;
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // File selected
    videoInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    function handleFile(file) {
        const fileInfo = document.querySelector('.drop-zone p');
        fileInfo.innerHTML = `📄 ${file.name}<br><span style="font-size:0.8rem;color:#8888aa;">${(file.size / 1024 / 1024).toFixed(1)} MB</span>`;
        generateBtn.style.display = 'block';
        generateBtn.textContent = '⚡ Generate Subtitles';
        generateBtn.disabled = false;
    }

    generateBtn.addEventListener('click', async function() {
        const file = videoInput.files[0];
        if (!file) {
            subtitlePreview.textContent = '❌ Please upload a video file first!';
            subtitlePreview.style.color = '#ff6b6b';
            return;
        }

        subtitlePreview.textContent = '⏳ Processing... Please wait.';
        subtitlePreview.style.color = '#a8a8d8';
        generateBtn.disabled = true;
        generateBtn.textContent = '⏳ Processing...';
        downloadBtn.style.display = 'none';

        const formData = new FormData();
        formData.append('video', file);
        formData.append('source_language', sourceLang.value);
        formData.append('target_language', targetLang.value);
        formData.append('translate', 'true');

        try {
            // Use your Railway backend URL
            const response = await fetch('https://ai-subtitle-generator-production-650b.up.railway.app/api/transcribe', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            
            // Get filename from response
            const contentDisposition = response.headers.get('content-disposition');
            let filename = 'subtitles.srt';
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="?([^"]+)"?/);
                if (match) filename = match[1];
            }

            // Show preview
            const text = await blob.text();
            subtitlePreview.textContent = text.substring(0, 2000) + (text.length > 2000 ? '\n\n... (truncated)' : '');
            subtitlePreview.style.color = '#d0d0e0';
            
            // Setup download
            currentSrt = text;
            downloadBtn.style.display = 'inline-block';
            downloadBtn.onclick = function() {
                const blob = new Blob([currentSrt], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            };

            subtitlePreview.textContent = '✅ Done! ' + subtitlePreview.textContent;

        } catch (error) {
            console.error('Error:', error);
            subtitlePreview.textContent = '❌ Error: ' + error.message;
            subtitlePreview.style.color = '#ff6b6b';
        } finally {
            generateBtn.disabled = false;
            generateBtn.textContent = '⚡ Generate Subtitles';
        }
    });
});
