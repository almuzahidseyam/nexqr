const {test} = require('node:test');
const assert = require('node:assert/strict');
require('../static/crypto.js');
test('unicode roundtrip, random salts/nonces, wrong password and tampering', async () => {
  const message = 'বাংলা <script>alert(1)</script>', password = 'long unique passphrase';
  const first = await NexCrypto.encrypt(message,password), second = await NexCrypto.encrypt(message,password);
  assert.notEqual(first,second);
  assert.equal(await NexCrypto.decrypt(first,password),message);
  await assert.rejects(NexCrypto.decrypt(first,'a wrong password'));
  const modified = JSON.parse(first); const data = Buffer.from(modified.data,'base64'); data[0] ^= 1; modified.data = data.toString('base64');
  await assert.rejects(NexCrypto.decrypt(JSON.stringify(modified),password));
});
test('reject invalid envelopes and weak creation passwords', async () => {
  await assert.rejects(NexCrypto.encrypt('a message','short'));
  await assert.rejects(NexCrypto.encrypt('','long unique passphrase'));
  await assert.rejects(NexCrypto.decrypt('{"v":999}','password'));
});
test('vendored helper decodes legacy CryptoJS messages', () => {
  const legacy = require('../static/vendor/crypto-js.js');
  const ciphertext = legacy.AES.encrypt('legacy content','legacy password').toString();
  assert.equal(legacy.AES.decrypt(ciphertext,'legacy password').toString(legacy.enc.Utf8),'legacy content');
});
