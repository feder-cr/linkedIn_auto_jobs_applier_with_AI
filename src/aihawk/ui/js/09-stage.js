/* ---- the stage: one screen, or two ----
   Which browsers are on it and in what order: the one being watched first,
   then the rest as the server lists them. So clicking any screen or any chip
   brings that browser to the front, and at one-up that means it fills the
   stage - which is what "click it and go to another screen" means. */
function onStage(){
  const w = watched();
  const live = stage.fleet.filter(b => b.running);
  const first = live.filter(b => b.id === w);
  return first.concat(live.filter(b => b.id !== w)).slice(0, stage.grid);
}

/* ⛔ A BLOB URL IS NOT GARBAGE-COLLECTED WITH ITS ELEMENT. Every frame is
   an object URL, and the rebuild path threw its <img> away without revoking:
   the stage redraws whenever the agent moves to another browser - which it
   does on its own - so a long run leaked one full window capture per pane per
   switch, held until the tab closes. */
function dropFrames(box){
  for(const im of box.querySelectorAll('img')){
    if(im.src && im.src.startsWith('blob:')) URL.revokeObjectURL(im.src);
  }
}

function blank(cell, why){
  const im = cell.querySelector('img'); if(im) im.hidden = true;
  setState(cell, 'nopage', why || 'no tab open',
           'ask the agent to open a page here');
  cell.dataset.blank = '1';
  cell.dataset.at = '';
}

/* One screen: a frame that wraps the picture, the name written on it, and
   whatever the picture cannot say written over it. */
function screenFor(b, current){
  const cell = document.createElement('button');
  cell.type = 'button'; cell.className = 'screen'; cell.dataset.id = b.id;
  cell.setAttribute('aria-current', String(current));
  /* The NAME is the action and the state is the description. With the name
     taken from the contents, a screen reader heard the address, the tag and
     the veil's sentence run together, and `title` was never the name. */
  cell.title = 'Watch ' + b.id;
  cell.setAttribute('aria-label', 'Watch ' + b.id);
  const box = el('div','frame');
  const im = document.createElement('img'); im.alt = ''; im.hidden = true;
  const tag = el('span','tag');
  tag.appendChild(el('span','id', b.id));
  /* The one the agent is driving, marked rather than selected: the person's
     eye and the agent's hand are two different things and the tag says both. */
  if(b.id === stage.focus){
    const dot = el('span','dot');
    dot.title = 'the agent is working here';
    tag.appendChild(dot);
  }
  const stamp = el('span','stamp'); stamp.hidden = true;
  const veil = el('div','veil'); veil.id = 'veil-' + b.id;
  cell.setAttribute('aria-describedby', veil.id);
  box.append(im, veil, tag, stamp);
  cell.appendChild(box);
  /* Three states and not two, and the third is the one that reads as a
     failure: a browser that is RUNNING WITH NO TAB cannot be captured - the
     engine refuses, saying it has no page open - and asking anyway spends a
     round trip to be told so. The tabs are already in the answer this was
     built from, so the question is asked of data rather than of the pipe. */
  const has = (b.urls || []).length > 0;
  if(has) setState(cell, 'waiting', 'waiting for the first frame');
  else { setState(cell, 'nopage', 'no tab open',
                  'ask the agent to open a page here');
         cell.dataset.blank = '1'; }
  cell.onclick = () => watchThis(b.id);
  return cell;
}

function drawStage(){
  const box = $('stage'), show = onStage();
  /* The template follows the cells that exist: `grid` is derived from the
     running browsers in `drawFleet`, so this is one or two, never a promise of
     more cells than there are. */
  box.dataset.grid = String(Math.min(stage.grid, Math.max(1, show.length)));
  /* Only when the SET changes, or every poll would throw away the pictures and
     make the whole stage flash once a second for no new fact. */
  const sig = show.map(b => b.id + ((b.urls || []).length ? 'p' : '')
                            + (b.id === stage.focus ? 'a' : '')).join(',')
              + '|' + stage.grid + '|' + watched();
  if(box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  dropFrames(box);
  box.textContent = '';
  stage.turn = 0;
  /* ⛔ THE QUESTION IS 'IS THERE ANYTHING TO SEE', NOT 'ARE THERE
     BROWSERS'. With a browser running and no tab open, the bar stayed fully
     armed - address, Live/Frozen and the word IDLE - over a stage whose own
     words were `no tab open`. A screen with nothing on it is the same empty
     room to the person looking at it. */
  const anything = show.some(b => (b.urls || []).length);
  right.dataset.empty = anything ? '' : '1';
  /* Not decoration: `inert` removes them from the tab order and from the
     accessibility tree, which is what 'this control cannot do anything right
     now' has to mean for somebody who is not using a mouse. */
  $('mode').inert = !anything;
  if(!show.length){
    /* An empty state that only reports the emptiness leaves the person to
       guess where the button is. There is no button - browsers are opened by
       asking - so this is the one place that has to say so, and to show the
       shape of the sentence that does it. */
    box.appendChild(emptyCell.cloneNode(true));
    return;
  }
  for(const b of show) box.appendChild(screenFor(b, b.id === watched()));
}

/* Taken before anything can empty the stage: the same three lines used to be
   built here AND described in the markup, which is one sentence in two
   places waiting to disagree. */
const emptyCell = $('stage').firstElementChild.cloneNode(true);

async function drawFleet(){
  let got = {browsers: []};
  try { const r = await door('/live/browsers', {cache:'no-store'});
        if(r.ok) got = await r.json(); }
  catch(err){ return; }
  stage.fleet = got.browsers || [];
  stage.focus = got.focus || '';
  /* ⛔ THE LAYOUT IS NOT CHOSEN ANY MORE, IT FOLLOWS THE BROWSERS. There was a
     picker - one, two or four screens - because a session could hold eight and
     which ones to watch was a decision. A session holds `main` and, while it is
     needed, `support`: two screens when the helper is up, one when it is not,
     and nothing for a person to set. A control that chose between layouts of
     the same single screen is the defect this page has written down twice. */
  stage.grid = stage.fleet.filter(b => b.running).length >= 2 ? 2 : 1;
  drawStage();
  drawStrip();
}

/* ⛔ SEPARATE FROM THE POLL, because changing what is watched changes what
   the strip holds and there is nothing to ask the server about it. While this
   lived inside `drawFleet` the strip stayed wrong until the next poll landed -
   up to three seconds showing a browser that was already on the stage. It
   reads the fleet that is already here. */
function drawStrip(){
  /* The strip carries what the stage does not. With both browsers running the
     stage holds both and the strip is empty; with one running, the declared
     other is a chip here. */
  const up = new Set(onStage().map(b => b.id));
  const others = stage.fleet.filter(b => !up.has(b.id));
  const box = $('thumbs');
  /* Only when the SET changes, or the row would flash once a poll for no new
     fact. */
  const sig = others.map(b => b.id + (b.running ? '1' : '0') + (b.id === stage.focus ? 'a' : ''))
                    .join(',') + '|' + watched() + '|' + stage.grid;
  if(box.dataset.sig !== sig){
    box.dataset.sig = sig;
    box.textContent = '';
    for(const b of others) box.appendChild(chipFor(b));
  }
  box.hidden = others.length === 0;
}

/* Whatever was waiting when the page went away comes back into the composer
   rather than into the queue: the run it was queued behind is over, so the
   honest place for it is where somebody can read it and press send. */
const waiting_text = queuedFromBefore();
if(waiting_text){ i.value = waiting_text; setQueued(null);
                  i.style.height = 'auto';
                  i.style.height = Math.min(i.scrollHeight, 200) + 'px'; }
