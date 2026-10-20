"""The locked page works offline and sends only JSON to this origin."""

REQUEST_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Whisperwick</title><style>
/* The 3D page's parchment colours, so the first page a stranger sees matches the game. */
:root{color-scheme:light}
body{max-width:32rem;margin:3rem auto;padding:1rem;font:15px/1.6 system-ui,sans-serif;
background:#e7dbc1;color:#493f32}h1{font:600 30px Fraunces,"Iowan Old Style",Georgia,serif}
label,input,textarea{display:block;margin:.6rem 0}
input,textarea{width:95%;font:inherit;color:inherit;
background:#f8eed8;border:1px solid #c9b89b;border-radius:10px;padding:8px 10px}
button{font:inherit;font-weight:600;min-height:40px;padding:8px 16px;border-radius:10px;
cursor:pointer;background:#65765a;color:#fff8e8;border:1px solid #56664c}
</style></head><body><h1>Whisperwick</h1><p>Ask for the link with the key.</p>
<p>Request an invitation. Your name and note go to the host.</p>
<form id="request"><label>Name <input name="name" required minlength="1" maxlength="40"
autocomplete="name"></label><label>Note (optional)
<textarea name="note" maxlength="300" rows="4"></textarea></label>
<button>Request invitation</button></form><p id="status" role="status"></p>
<script>
const form=document.getElementById('request'), status=document.getElementById('status');
form.onsubmit=async event=>{
  event.preventDefault();const button=form.querySelector('button');button.disabled=true;
  try{
    const response=await fetch('/request',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:form.elements.name.value,note:form.elements.note.value})});
    status.textContent=await response.text();
  }catch(error){status.textContent='Could not send request. Please try again.';}
  button.disabled=false;
};
</script></body></html>"""
