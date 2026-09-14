/* ---------------- the workspace ----------------
   What the right half of the page is showing, in ONE place. Two of these are
   the server's and two are this page's own, and keeping them in one object is
   what makes that legible: `fleet` is which browsers this session holds and
   `focus` is the one the AGENT is driving, both read from `/live/browsers`
   every three seconds; `pinned` is the screen the PERSON chose to watch, and
   `grid` how many screens the stage shows, which follows the browsers that are
   running. `turn` is which screen the frame pump asks next.

   Until 0.52.0 these were six top-level variables across three files, one of
   them called `pinned2` because `pinned` was already taken by the transcript's
   scroll - a name that said "there was a clash" and nothing else.

   ⛔ TWO DIFFERENT THINGS, AND THEY USED TO BE ONE. `focus` is the browser the
   AGENT drives - it lives on the server and only the agent moves it, by being
   asked. `pinned` is the pane the PERSON is looking at, which is this page's
   own business and nobody else's.

   They were the same value until somebody said everything should be commanded
   from the chat, and folding them together is what made clicking a pane a
   COMMAND. Now the big pane follows the agent, which is what you want while it
   works, and looking somewhere else is a choice that sticks until you undo it. */
const stage = {fleet: [], focus: '', pinned: null, grid: 1, turn: 0};
const watched = () => stage.pinned || stage.focus;

/* A browser that is not on the stage is drawn as a NAME: a chip saying which
   browser it is and whether it is running, that asks to watch it when clicked.

   ⛔ AND NOT AS A PICTURE FRAME. Six declared but stopped browsers used to
   draw six 168x133 cards, each with the words `not up` in the middle of an
   empty rectangle - a gallery of failures under the stage, in the place the
   running ones live. A thing with no image is a name, and the row is a list
   of what this session holds.

   There is no picture branch here any more, because there is nothing for it
   to draw: the stage holds as many screens as there are running browsers, up
   to the two a session can have, so a running browser is always ON the stage
   and the strip only ever holds the declared one that has not started. The
   preview loop that refreshed pictures in this row - one pane every 400 ms,
   in turn - was refreshing a row that could not contain one, and went with
   the branch. */
function chipFor(b){
  const chip = document.createElement('button');
  chip.type = 'button'; chip.className = 'chip'; chip.dataset.id = b.id;
  /* The state goes into the name, from the one place that already knows it:
     "not running" was a 6px ring and nothing else, no text anywhere. */
  const state = b.running ? 'running' : 'not running';
  chip.title = 'Watch ' + b.id + ' - ' + state;
  chip.setAttribute('aria-label', 'Watch ' + b.id + ' - ' + state);
  /* Clicking a chip changes what the address bar and the stage follow, and
     the mark says so, as it does on the screens above. */
  chip.setAttribute('aria-current', String(b.id === watched()));
  if(!b.running) chip.appendChild(el('span','off'));
  chip.appendChild(el('span','id', b.id));
  if(b.id === stage.focus){
    const dot = el('span','dot');
    dot.title = 'the agent is working here';
    chip.appendChild(dot);
  }
  chip.onclick = () => watchThis(b.id);
  return chip;
}

/* Looking, not commanding. Clicking the pane you are already watching gives
   the view back to the agent, so there is a way out of a choice as well as in.
   Nothing is sent: what the person looks at is not the agent's business. */
function watchThis(id){
  stage.pinned = (stage.pinned === id) ? null : id;
  drawStage(); drawStrip(); paintWhere();
}
