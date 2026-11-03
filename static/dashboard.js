const form = document.getElementById('qr-form');
const type = document.getElementById('type');
function fields() {
  document.getElementById('name-fields').hidden = type.value === 'standard';
  document.getElementById('url-fields').hidden = type.value === 'secure';
  document.getElementById('url').required = type.value !== 'secure';
  document.getElementById('secure-fields').hidden = type.value !== 'secure';
  document.getElementById('art-fields').hidden = type.value !== 'artistic';
}
type.addEventListener('change',fields); fields();
form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('submit-btn'), status = document.getElementById('status');
  button.disabled = true; status.textContent = 'Generating…'; status.dataset.error = 'false';
  document.getElementById('result').hidden = true; document.getElementById('empty-state').hidden = false;
  try {
    const data = new FormData(form);
    if (type.value === 'secure') data.set('encrypted_payload', await NexCrypto.encrypt(document.getElementById('payload').value, document.getElementById('password').value));
    const response = await fetch(form.action,{method:'POST',body:data,signal:AbortSignal.timeout(120000)});
    if (response.status === 403) throw new Error('This action is unavailable or your session expired. Refresh and sign in again.');
    const result = await response.json();
    if (!response.ok || result.status !== 'success') throw new Error(result.message || 'Generation failed.');
    document.getElementById('qr-result').src = result.qr_image;
    document.getElementById('download-btn').href = result.qr_image;
    const link = document.getElementById('qr-link'); link.href = result.target_url; link.textContent = result.target_url;
    document.getElementById('result').hidden = false; document.getElementById('empty-state').hidden = true;
    document.getElementById('password').value = ''; document.getElementById('payload').value = '';
    status.textContent = 'Ready to download. Check your QR before sharing.';
  } catch(error) { status.textContent = error.name === 'TimeoutError' ? 'Request timed out. Check saved codes before retrying; an artistic request may still incur charges.' : error.message; status.dataset.error = 'true'; }
  finally { button.disabled = false; }
});
