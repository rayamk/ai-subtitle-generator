// Colab URL ကို ထည့်ပါ (အဆုံးမှာ / မပါပါစေနဲ့)
const BACKEND_URL = 'https://5000-xxxx-xxxx-xxxx-xxxx.xxxx.colab.dev';

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    const status = document.getElementById('status');
    const downloadLink = document.getElementById('downloadLink');
    
    if (!form) {
        console.error('Form element #uploadForm မတွေ့ပါ');
        return;
    }
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('videoFile');
        const file = fileInput ? fileInput.files[0] : null;
        
        if (!file) {
            status.textContent = '❌ ကျေးဇူးပြု၍ ဗီဒီယိုဖိုင်ကို အရင်ရွေးချယ်ပေးပါ။';
            return;
        }
        
        status.textContent = '⏳ လုပ်ဆောင်နေပါသည်... (ခဏစောင့်ပေးပါ)';
        downloadLink.style.display = 'none';
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // URL ကို မှန်ကန်စွာ ပေါင်းစပ်ခြင်း
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
                downloadLink.textContent = '📥 မြန်မာ SRT ဖိုင်ကို ရယူရန် နှိပ်ပါ';
                status.textContent = '✅ အောင်မြင်စွာ လုပ်ဆောင်ပြီးပါပြီ။';
            } else {
                const errorText = await response.text();
                status.textContent = `❌ Error: ${response.status} - ${errorText}`;
            }
        } catch (error) {
            status.textContent = '❌ Server နှင့် ချိတ်ဆက်၍ မရပါ။ Colab အလုပ်လုပ်နေရဲ့လား စစ်ဆေးပေးပါ။';
            console.error('Fetch error:', error);
        }
    });
});
