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
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                subtitlePreview.textContent = '❌ Error: ' + data.error;
                return;
            }

            currentSrt = data.srt;
            
            // FIX: Display the actual preview, not an error!
            subtitlePreview.textContent = data.preview || data.srt;
            
            downloadBtn.style.display = 'inline-block';
            
        } catch (error) {
            console.error(error);
            subtitlePreview.textContent = '❌ Error: ' + error.message;
        }
    });

    downloadBtn.addEventListener('click', function() {
        if (!currentSrt) {
            alert('No subtitles to download!');
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
