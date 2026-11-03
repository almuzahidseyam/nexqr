chrome.tabs.query({active:true,currentWindow:true}, tabs => {
  const tab = tabs?.[0], label = document.getElementById('current-url'), button = document.getElementById('generate-btn');
  if (!tab?.url || !/^https?:\/\//.test(tab.url)) {label.textContent = 'Open an HTTP or HTTPS page first.'; return;}
  label.textContent = tab.url; button.disabled = false;
  button.addEventListener('click', () => {
    const target = new URL('http://127.0.0.1:8000/');
    target.searchParams.set('url',tab.url); target.searchParams.set('name',(tab.title || '').slice(0,100));
    chrome.tabs.create({url:target.href});
  });
});
