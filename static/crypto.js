/* AES-GCM with per-message randomness; no third-party network scripts. */
globalThis.NexCrypto = (() => {
  const encode = b => btoa(String.fromCharCode(...new Uint8Array(b)));
  const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  async function key(password, salt) {
    const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:600000, hash:'SHA-256'}, material, {name:'AES-GCM', length:256}, false, ['encrypt','decrypt']);
  }
  async function encrypt(text, password) {
    if (password.length < 12 || text.length > 4000 || !text) throw new Error('Use a message of 1–4000 characters and a password of at least 12 characters.');
    const salt = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12));
    const data = await crypto.subtle.encrypt({name:'AES-GCM', iv}, await key(password,salt), new TextEncoder().encode(text));
    return JSON.stringify({v:2, salt:encode(salt), iv:encode(iv), data:encode(data)});
  }
  async function decrypt(payload, password) {
    if (payload.length > 10000) throw new Error('Payload too large.');
    const value = JSON.parse(payload);
    if (value.v !== 2 || typeof value.salt !== 'string' || typeof value.iv !== 'string' || typeof value.data !== 'string') throw new Error('Invalid envelope.');
    const salt = decode(value.salt), iv = decode(value.iv), data = decode(value.data);
    if (salt.length !== 16 || iv.length !== 12 || data.length < 16) throw new Error('Invalid envelope.');
    return new TextDecoder('utf-8',{fatal:true}).decode(await crypto.subtle.decrypt({name:'AES-GCM', iv}, await key(password,salt), data));
  }
  return {encrypt,decrypt};
})();
