document.getElementById('unlock-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.target.querySelector('button'), status = document.getElementById('status');
  button.disabled = true;
  try {
    const payload = JSON.parse(document.getElementById('encrypted-data').textContent);
    const password = document.getElementById('password').value;
    let text;
    if (payload.startsWith('{')) text = await NexCrypto.decrypt(payload,password);
    else {
      text = CryptoJS.AES.decrypt(payload,password).toString(CryptoJS.enc.Utf8);
      if (!text) throw new Error('Invalid legacy message');
      document.getElementById('legacy-note').hidden = false;
    }
    const output = document.getElementById('decrypted-text'); output.textContent = text; output.hidden = false;
    event.target.hidden = true; document.getElementById('password').value = ''; status.textContent = '';
  } catch {status.textContent = 'Incorrect password or damaged message.'; status.dataset.error = 'true';}
  finally {button.disabled = false;}
});
