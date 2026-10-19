// Shared with the inline 2D page. Feedback has its own request, never an action.
export function setupFeedback(page, preview = false) {
  const node = (tag, text) => {
    const n = document.createElement(tag); n.textContent = text; return n;
  };
  const dialog = node('dialog', ''); dialog.className = 'feedback-dialog';
  dialog.setAttribute('aria-labelledby', 'feedback-title');
  const title = node('h2', 'Feedback'); title.id = 'feedback-title';
  const form = node('form', '');
  const ratingLabel = node('label', 'Rating (optional) ');
  const rating = node('select', ''); rating.setAttribute('aria-label', 'Rating (optional)');
  rating.append(new Option('No rating', ''));
  for (let i = 1; i <= 5; i++) rating.append(new Option(String(i), String(i)));
  ratingLabel.append(rating);
  const tags = node('fieldset', ''); tags.append(node('legend', 'Quick tags'));
  for (const tag of ['confusing', 'too slow', 'villagers ignored me', 'bug', 'loved it']) {
    const label = node('label', '');
    const input = node('input', ''); input.type = 'checkbox'; input.value = tag;
    label.append(input, document.createTextNode(tag)); tags.append(label);
  }
  const textLabel = node('label', 'Tell us more (up to 2000 characters)');
  const text = node('textarea', ''); text.maxLength = 2000; text.rows = 5;
  textLabel.append(text);
  const status = node('p', ''); status.setAttribute('role', 'status');
  const send = node('button', 'Send'); send.type = 'submit';
  const cancel = node('button', 'Cancel'); cancel.type = 'button';
  cancel.onclick = () => dialog.close();
  form.append(ratingLabel, tags, textLabel, status, send, cancel);
  dialog.append(title, form); document.body.append(dialog);
  form.onsubmit = async e => {
    e.preventDefault();
    if (preview) { status.textContent = 'Fixture preview: no feedback is sent.'; return; }
    send.disabled = true;
    try {
      const r = await fetch('/feedback', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({page, rating: rating.value ? Number(rating.value) : null,
          tags: [...tags.querySelectorAll('input:checked')].map(x => x.value), text: text.value})});
      const data = await r.json();
      status.textContent = r.ok ? 'Thanks, saved.' : data.error;
      if (r.ok) { form.reset(); cancel.textContent = 'Close'; }
      else send.disabled = false;
    } catch {
      status.textContent = 'Could not save feedback. Please try again.'; send.disabled = false;
    }
  };
  const open = () => {
    status.textContent = ''; send.disabled = false; cancel.textContent = 'Cancel';
    if (!dialog.open) dialog.showModal();
  };
  document.querySelectorAll('[data-feedback]').forEach(button => button.onclick = open);
  return open;
}
