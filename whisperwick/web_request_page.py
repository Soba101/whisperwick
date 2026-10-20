"""The locked page works offline and sends only JSON to this origin."""

# What the page says at the top, by the state of this browser's request ticket (2026-10-21).
STATUS = {
    "": "<p>Ask for the link with the key.</p>",
    "waiting": ("<p class='note'><b>Your request is waiting for approval.</b> Come back to this "
                "page later: once you are approved you go straight in.</p>"),
    "closed": ("<p class='note'><b>This request was not approved, or is no longer waiting.</b> "
               "You can send a new request below.</p>"),
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Whisperwick</title><style>
/* The 3D page's parchment colours, so the first page a stranger sees matches the game. */
:root{color-scheme:light}
body{max-width:32rem;margin:3rem auto;padding:1rem;font:15px/1.6 system-ui,sans-serif;
background:#e7dbc1;color:#493f32}h1{font:600 30px Fraunces,"Iowan Old Style",Georgia,serif}
h2{font:600 19px Fraunces,"Iowan Old Style",Georgia,serif;margin-top:2rem}
label,input,textarea{display:block;margin:.6rem 0}
input,textarea{width:95%;font:inherit;color:inherit;
background:#f8eed8;border:1px solid #c9b89b;border-radius:10px;padding:8px 10px}
button{font:inherit;font-weight:600;min-height:40px;padding:8px 16px;border-radius:10px;
cursor:pointer;background:#65765a;color:#fff8e8;border:1px solid #56664c}
.note{background:#f8eed8;border:1px solid #c9b89b;border-radius:12px;padding:12px 14px}
#code{font:600 22px ui-monospace,Menlo,monospace;letter-spacing:2px}
</style></head><body><h1>Whisperwick</h1>@STATUS@
<p>Request an invitation. Your name and note go to the host.</p>
<form id="request"><label>Name <input name="name" required minlength="1" maxlength="40"
autocomplete="name"></label><label>Note (optional)
<textarea name="note" maxlength="300" rows="4"></textarea></label>
<button>Request invitation</button></form><div id="status" role="status"></div>
<h2>Have a code?</h2>
<p>Requested on another device? Type the code you were given to check in here.</p>
<form id="have-code"><label>Code <input name="code" required maxlength="16"
autocomplete="off" autocapitalize="characters" placeholder="ABCD-EFG-HJK"></label>
<button>Check in</button></form><p id="code-status" role="status"></p>
<script>
const form=document.getElementById('request'), status=document.getElementById('status');
form.onsubmit=async event=>{
  event.preventDefault();const button=form.querySelector('button');button.disabled=true;
  try{
    const response=await fetch('/request',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:form.elements.name.value,note:form.elements.note.value})});
    const text=await response.text(), code=response.headers.get('X-Request-Code');
    status.replaceChildren();
    const line=document.createElement('p');line.textContent=text;status.append(line);
    if(code){
      // The code is shown, not stored in page storage; this browser keeps the ticket itself.
      const note=document.createElement('p');note.className='note';
      note.textContent='Come back to this page later. Once you are approved you go straight in. '
        +'On another device, use this code:';
      const box=document.createElement('p');box.id='code';box.textContent=code;
      status.append(note,box);
    }
  }catch(error){status.textContent='Could not send request. Please try again.';}
  button.disabled=false;
};
const codeForm=document.getElementById('have-code');
const codeStatus=document.getElementById('code-status');
codeForm.onsubmit=async event=>{
  event.preventDefault();
  try{
    const response=await fetch('/request/code',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({code:codeForm.elements.code.value})});
    if(response.ok){location.reload();return;}
    codeStatus.textContent=await response.text();
  }catch(error){codeStatus.textContent='Could not check the code. Please try again.';}
};
</script></body></html>"""


def request_page(status: str = "") -> str:
    return PAGE.replace("@STATUS@", STATUS.get(status, STATUS[""]))


# The page with no request yet, as before (tests and older callers).
REQUEST_PAGE = request_page()
