// Secrets live only in this page. Never save them in storage or browser history.
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const notice = document.getElementById('notice');
const linkBox = document.getElementById('personal-link');
const linkValue = document.getElementById('link-value');
const copyStatus = document.getElementById('copy-status');
let busy = false;

function clearLink() {
  linkValue.value = '';
  copyStatus.textContent = '';
  linkBox.hidden = true;
}
window.addEventListener('pagehide', clearLink);
document.getElementById('dismiss').onclick = clearLink;
document.getElementById('copy').onclick = async () => {
  try {
    await navigator.clipboard.writeText(linkValue.value);
    copyStatus.textContent = 'Copied.';
  } catch (error) {
    // Clipboard access may be unavailable on local HTTP or denied by the browser.
    linkValue.focus();
    linkValue.select();
    linkValue.setSelectionRange(0, linkValue.value.length);
    copyStatus.textContent = 'Link selected. Use your device’s Copy command.';
  }
};

async function refresh() {
  const response = await fetch('/admin', {cache:'no-store'});
  if (!response.ok) throw new Error('Could not refresh. Reload the page.');
  // This is escaped HTML from our owner route, never client-supplied markup.
  const page = new DOMParser().parseFromString(await response.text(), 'text/html');
  document.getElementById('admin-content').replaceWith(page.getElementById('admin-content'));
}

async function act(action, body, button) {
  if (busy) return;
  busy = true;
  button.disabled = true;
  notice.textContent = 'Saving…';
  try {
    const response = await fetch('/admin/' + action, {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf},
      body:JSON.stringify(body), cache:'no-store'
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save change.');
    if (result.link) {
      clearLink();
      linkValue.value = result.link;
      linkBox.hidden = false;
      linkValue.focus();
      linkValue.select();
    }
    notice.textContent = 'Saved.';
    try { await refresh(); }
    catch (error) { notice.textContent = 'Saved. Refresh to update the lists.'; }
  } catch (error) {
    notice.textContent = error.message || 'Could not save change. Please try again.';
  } finally {
    busy = false;
    button.disabled = false;
  }
}

// Delegation keeps controls working after the lists are refreshed.
document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button || busy) return;
  if (button.id === 'refresh') {
    busy = true;
    button.disabled = true;
    try { await refresh(); notice.textContent = 'Updated.'; }
    catch (error) { notice.textContent = error.message; }
    finally { busy = false; button.disabled = false; }
  } else if (button.hasAttribute('data-confirm')) {
    button.hidden = true;
    const confirm = button.closest('article').querySelector('.confirm');
    confirm.hidden = false;
    confirm.querySelector('button').focus();
  } else if (button.hasAttribute('data-cancel')) {
    const article = button.closest('article');
    article.querySelector('.confirm').hidden = true;
    const revoke = article.querySelector('[data-confirm]');
    revoke.hidden = false;
    revoke.focus();
  } else if (button.dataset.action) {
    const body = button.dataset.action === 'stop' ? {id:button.dataset.id}
                                                 : {name:button.dataset.name};
    await act(button.dataset.action, body, button);
  }
});
document.addEventListener('submit', async event => {
  if (event.target.id !== 'invite') return;
  event.preventDefault();
  const form = event.target;
  await act('invite', {name:form.elements.name.value}, form.querySelector('button'));
});
