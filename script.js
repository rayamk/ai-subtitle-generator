document.addEventListener('DOMContentLoaded', function() {
    const videoInput = document.getElementById('videoInput');
    const generateBtn = document.getElementById('generateBtn');
    const subtitlePreview = document.getElementById('subtitlePreview');
    const downloadBtn = document.getElementById('downloadBtn');
    const sourceLang = document.getElementById('sourceLang');
    const targetLang = document.getElementById('targetLang');

    let currentSrt = '';

    generateBtn.addEventListener('click', async function() {
        const file = videoInput.files[0];
        if (!file) {
            alert('Please upload a video file first!');
            return;
        }

        subtitlePreview.textContent = '⏳ Processing... Please wait!';

        const formData = new FormData();
        formData.append('video', file);
        formData.append('source_language', sourceLang.value);
        formData.append('target_language', targetLang.value);

        try {
            // Use the correct backend URL
            const backendUrl = 'https://ai-subtitle-generator-production-650b.up.railway.app';
            
            console.log('Sending request to:', backendUrl + '/api/transcribe');
            
            const response = await fetch(backendUrl + '/api/transcribe', {
                method: 'POST',
                body: formData,
                // Add these headers for better compatibility
                headers: {
                    'Accept': 'application/json',
                },
                mode: 'cors' // Explicitly enable CORS
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.error) {
                subtitlePreview.textContent = '❌ Error: ' + data.error;
                return;
            }

            currentSrt = data.srt;
            subtitlePreview.textContent = data.preview || data.srt;
            downloadBtn.style.display = 'inline-block';

        } catch (error) {
            console.error('Error details:', error);
            subtitlePreview.textContent = '❌ Error: ' + error.message + '\n\nMake sure the backend is running at:\nhttps://ai-subtitle-generator-production-650b.up.railway.app';
        }
    });

    downloadBtn.addEventListener('click', function() {
        if (!currentSrt) {
            alert('No subtitles to download! Generate subtitles first.');
            return;
        }

        const blob = new Blob([currentSrt], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'subtitles.srt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
});
