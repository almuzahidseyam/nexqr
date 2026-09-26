document.addEventListener('DOMContentLoaded', () => {
    let currentUrl = '';
    let currentTitle = '';

    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        if (!tabs || !tabs[0] || !tabs[0].url) {
            document.getElementById('current-url').innerText = "Unable to get tab URL.";
            document.getElementById('generate-btn').disabled = true;
            return;
        }
        
        currentUrl = tabs[0].url;
        currentTitle = tabs[0].title || 'Extension Generated QR';
        
        // Prevent extension from running on internal chrome pages
        if (currentUrl.startsWith('chrome://') || currentUrl.startsWith('edge://')) {
            document.getElementById('current-url').innerText = "Cannot generate QR for internal browser pages.";
            document.getElementById('generate-btn').disabled = true;
            return;
        }
        
        document.getElementById('current-url').innerText = currentUrl;
    });

    document.getElementById('generate-btn').addEventListener('click', async () => {
        const btn = document.getElementById('generate-btn');
        btn.innerText = "Syncing with Server...";
        btn.disabled = true;

        const formData = new FormData();
        formData.append('url', currentUrl);
        formData.append('name', currentTitle);

        try {
            const res = await fetch("http://127.0.0.1:8000/api/generate/", {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                document.getElementById('qr-image').src = data.qr_image;
                document.getElementById('qr-container').style.display = 'block';
                btn.style.display = 'none';
            } else {
                alert("Server error: " + data.message);
                btn.innerText = "Try Again";
                btn.disabled = false;
            }
        } catch(err) {
            alert("Error: Ensure your NexQR Django server is running on http://127.0.0.1:8000/");
            btn.innerText = "Try Again";
            btn.disabled = false;
        }
    });
});
