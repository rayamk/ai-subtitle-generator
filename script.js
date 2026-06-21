// Colab URL ကို အောက်ပါအတိုင်း ထည့်ပါ
const BACKEND_URL = 'https://5000-m-s-kkb-use1c0-3nq7f7l5l8mn9-c.us-east1-0.prod.colab.dev';

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    const status = document.getElementById('status');
    const downloadLink = document.getElementById('downloadLink');
    
    if (!form) {
        console.error('Form not found!');
        return;
    }
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('videoFile');
        const file = fileInput.files[0];
        
        if (!file) {
            status.textContent = '❌ ဗီဒီယိုဖိုင် ရွေးပေးပါ။';
            return;
        }
        
        status.textContent = '⏳ လုပ်ဆောင်နေပါသည်...';
        downloadLink.style.display = 'none';
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // URL နှင့် path ကို ပေါင်းစပ်ထားသည်
            const response = await fetch(`${BACKEND_URL}/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                downloadLink.href = url;
                downloadLink.download = 'myanmar_subtitles.srt';
                downloadLink.style.display = 'block';
                downloadLink.textContent = '📥 မြန်မာ SRT ကို Download လုပ်ပါ';
                status.textContent = '✅ ပြီးပါပြီ။';
            } else {
                status.textContent = '❌ Error: ' + response.status;
            }
        } catch (error) {
            status.textContent = '❌ Server နှင့် ချိတ်ဆက်လို့မရပါ။';
            console.error('Fetch error:', error);
        }
    });
});
