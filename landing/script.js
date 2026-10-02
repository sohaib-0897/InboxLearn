/**
 * InboxLearn landing interactions — vanilla JavaScript, no dependencies.
 * Owners: WebGL loop owns the hero field; CSS transitions own reveals and the
 * workflow thread (toggled by IntersectionObserver); one RAF owns the cursor ring.
 */
(function () {
  'use strict';

  // Streamlit may re-insert this script; tear down the previous instance first.
  if (window.__inboxlearnLanding && typeof window.__inboxlearnLanding.destroy === 'function') {
    window.__inboxlearnLanding.destroy();
  }
  const cleanups = [];
  const listen = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    cleanups.push(() => target.removeEventListener(type, handler, options));
  };
  const page = document.getElementById('landing-page');
  if (!page) return;
  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
  const onQueryChange = (query, handler) => {
    if (query.addEventListener) {
      query.addEventListener('change', handler);
      cleanups.push(() => query.removeEventListener('change', handler));
    }
  };

  // --- Synthetic preview fixtures: never sent anywhere ---
  const DEMO_EMAILS = [
    {
      id: 1,
      sender: 'feedback-careers@example.test',
      date: 'Today, 09:14 AM',
      subject: 'Interview moved to Tuesday',
      snippet: 'The hiring team moved your software interview to Tuesday morning…',
      body: 'Hello,\n\nThe engineering hiring team has rescheduled your technical interview to Tuesday at 10:00 AM Eastern. Please confirm your availability or propose an alternative window via the applicant portal.\n\nBest regards,\nTalent Acquisition Team',
      predCategory: 'job opportunities',
      predPriority: 'high',
      confidence: '0.68',
      needsReview: true,
      reason: 'Below threshold (0.68 < 0.70 category confidence)',
      format: 'RFC 822 (.eml)'
    },
    {
      id: 2,
      sender: 'feedback-billing@example.test',
      date: 'Yesterday, 04:32 PM',
      subject: 'Rent invoice available',
      snippet: 'Your rent invoice is available with payment due on 5 October…',
      body: 'Notice: Your monthly residential lease invoice for October has been generated and posted to your resident ledger.\n\nTotal Due: $1,450.00\nDue Date: October 5, 2026\nGrace period ends October 10.\n\nPlease remit payment through the resident portal.',
      predCategory: 'bills',
      predPriority: 'high',
      confidence: '0.74',
      needsReview: false,
      reason: 'Above threshold (0.74 ≥ 0.70 category confidence)',
      format: 'RFC 822 (.eml)'
    },
    {
      id: 3,
      sender: 'feedback-campus@example.test',
      date: '2 days ago',
      subject: 'Academic transcript request',
      snippet: 'Please collect your academic transcript from the university office…',
      body: 'Dear Student,\n\nYour official university transcript request has been printed and certified. You may collect your sealed document from Student Administrative Services, Hall B, Room 104 during regular office hours (9:00 AM – 4:00 PM).\n\nOffice of the Registrar',
      predCategory: 'university',
      predPriority: 'normal',
      confidence: '0.59',
      needsReview: true,
      reason: 'Below threshold (0.59 < 0.70 category confidence)',
      format: 'MBOX archive'
    }
  ];

  let currentEmailIndex = 0;
  let simulatedCount = 0;
  let advanceTimer;

  function makeElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  }
  const byId = (id) => document.getElementById(id);
  // Streamlit's st.html sanitizer strips inline SVG, so decorative SVG is built here.
  const SVG_NS = 'http://www.w3.org/2000/svg';
  function svgElement(tag, attributes) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.keys(attributes).forEach((name) => element.setAttribute(name, attributes[name]));
    return element;
  }
  const brandMark = page.querySelector('.brand-mark');
  if (brandMark && !brandMark.querySelector('svg')) {
    const icon = svgElement('svg', { viewBox: '0 0 24 24', focusable: 'false', 'aria-hidden': 'true' });
    icon.append(svgElement('path', { d: 'M3.5 6.5h17v11h-17z M3.5 6.5l8.5 6.5 8.5-6.5', fill: 'none',
      stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linejoin': 'round' }));
    brandMark.append(icon);
  }

  // --- Mobile navigation ---
  const mobileToggle = byId('mobileNavToggle');
  const mobileDrawer = byId('mobileNavDrawer');
  function setDrawer(open) {
    mobileToggle.setAttribute('aria-expanded', String(open));
    mobileToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    mobileDrawer.hidden = !open;
  }
  if (mobileToggle && mobileDrawer) {
    listen(mobileToggle, 'click', () => setDrawer(mobileToggle.getAttribute('aria-expanded') !== 'true'));
    mobileDrawer.querySelectorAll('a').forEach((link) => listen(link, 'click', () => setDrawer(false)));
    listen(document, 'keydown', (event) => {
      if (event.key === 'Escape' && !mobileDrawer.hidden) { setDrawer(false); mobileToggle.focus(); }
    });
  }

  // --- Synthetic preview ---
  const emailListEl = byId('emailList');
  const detailSubject = byId('detailSubject');
  const detailSender = byId('detailSender');
  const detailDate = byId('detailDate');
  const detailFormat = byId('detailFormat');
  const detailBody = byId('detailBody');
  const statPredCategory = byId('statPredCategory');
  const statPredPriority = byId('statPredPriority');
  const statConfidence = byId('statConfidence');
  const statReviewStatus = byId('statReviewStatus');
  const changeSwitch = byId('changeLabelsSwitch');
  const switchState = byId('switchState');
  const categorySelect = byId('correctionCategory');
  const prioritySelect = byId('correctionPriority');
  const btnSave = byId('btnSaveCorrection');
  const statusMsg = byId('consoleStatusMsg');
  const counter = byId('ledgerCounter');

  function setSubmitLabel(text) {
    if (!btnSave) return;
    btnSave.replaceChildren(document.createTextNode(text + ' '), makeElement('span', '', '→'));
    btnSave.lastChild.setAttribute('aria-hidden', 'true');
  }

  // Adapted Uiverse key: off = keep the suggestion, on = edit the labels.
  function syncSwitch(resetToSuggestion) {
    const editing = Boolean(changeSwitch && changeSwitch.checked);
    const email = DEMO_EMAILS[currentEmailIndex];
    if (categorySelect) categorySelect.disabled = !editing;
    if (prioritySelect) prioritySelect.disabled = !editing;
    if (!editing && resetToSuggestion) {
      if (categorySelect) categorySelect.value = email.predCategory;
      if (prioritySelect) prioritySelect.value = email.predPriority;
    }
    if (switchState) switchState.textContent = editing ? 'On · not quite, I’ll change it' : 'Off · the suggestion looks right';
    setSubmitLabel(editing ? 'Simulate correction' : 'Simulate confirmation');
  }

  function renderEmail(index) {
    currentEmailIndex = index;
    const email = DEMO_EMAILS[index];
    if (!email) return;
    if (emailListEl) {
      emailListEl.querySelectorAll('.email-item-btn').forEach((button, idx) => {
        button.classList.toggle('is-active', idx === index);
        button.setAttribute('aria-pressed', idx === index ? 'true' : 'false');
      });
    }
    if (detailSubject) detailSubject.textContent = email.subject;
    if (detailSender) detailSender.textContent = email.sender;
    if (detailDate) detailDate.textContent = email.date;
    if (detailFormat) detailFormat.textContent = email.format;
    if (detailBody) detailBody.textContent = email.body;
    if (statPredCategory) statPredCategory.textContent = email.predCategory;
    if (statPredPriority) statPredPriority.textContent = email.predPriority;
    if (statConfidence) {
      statConfidence.replaceChildren(document.createTextNode(`${email.confidence} `),
        makeElement('span', 'uncalibrated-notice', '(uncalibrated estimate)'));
    }
    if (statReviewStatus) {
      const badge = makeElement('span', email.needsReview ? 'badge badge-accent' : 'badge badge-ink',
        email.needsReview ? 'Needs review' : 'Confident');
      const reason = makeElement('small', 'uncalibrated-notice', email.reason);
      reason.style.display = 'block';
      reason.style.marginTop = '.2rem';
      statReviewStatus.replaceChildren(badge, reason);
    }
    if (changeSwitch) changeSwitch.checked = false;
    syncSwitch(true);
    if (statusMsg) statusMsg.textContent = `Previewing synthetic email #${email.id}. Suggestions are illustrative; nothing is saved or trained.`;
  }

  if (emailListEl) {
    emailListEl.replaceChildren();
    DEMO_EMAILS.forEach((email, idx) => {
      const li = document.createElement('li');
      const button = makeElement('button', `email-item-btn${idx === 0 ? ' is-active' : ''}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', idx === 0 ? 'true' : 'false');
      const header = makeElement('div', 'email-item-header');
      header.append(makeElement('span', '', `#0${email.id}`), makeElement('span', '', email.date));
      const tags = makeElement('div', 'email-item-tags');
      tags.append(makeElement('span', 'email-item-tag', email.predCategory));
      if (email.needsReview) tags.append(makeElement('span', 'badge badge-accent', 'Review'));
      button.append(header, makeElement('div', 'email-item-subject', email.subject),
        makeElement('div', 'email-item-snippet', email.snippet), tags);
      listen(button, 'click', () => { window.clearTimeout(advanceTimer); renderEmail(idx); });
      li.append(button);
      emailListEl.appendChild(li);
    });
    renderEmail(0);
  }
  if (changeSwitch) listen(changeSwitch, 'change', () => syncSwitch(true));

  if (btnSave) {
    listen(btnSave, 'click', (event) => {
      event.preventDefault();
      const email = DEMO_EMAILS[currentEmailIndex];
      const category = categorySelect ? categorySelect.value : email.predCategory;
      const priority = prioritySelect ? prioritySelect.value : email.predPriority;
      const changed = category !== email.predCategory || priority !== email.predPriority;
      simulatedCount += 1;
      if (counter) counter.textContent = String(simulatedCount);
      if (statusMsg) {
        const label = makeElement('strong', '', '[PREVIEW ONLY]');
        statusMsg.replaceChildren(label, document.createTextNode(
          ` Simulated ${changed ? 'correction' : 'confirmation'} for #${email.id} (${category}, ${priority}). Nothing was saved or queued for training. Open the workspace to save real feedback.`));
      }
      btnSave.textContent = `✓ Previewed #${email.id}`;
      btnSave.disabled = true;
      window.clearTimeout(advanceTimer);
      advanceTimer = window.setTimeout(() => {
        btnSave.disabled = false;
        renderEmail((currentEmailIndex + 1) % DEMO_EMAILS.length);
      }, 1200);
    });
    cleanups.push(() => window.clearTimeout(advanceTimer));
  }

  // --- Hero shader: hand-written WebGL1, one owned RAF loop ---
  const VERTEX = 'attribute vec2 aPosition; varying vec2 vUv; void main(){ vUv = aPosition * 0.5 + 0.5; gl_Position = vec4(aPosition, 0.0, 1.0); }';
  const FRAGMENT = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform float uTime; uniform vec2 uResolution; varying vec2 vUv;
float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.0-2.0*f);
  return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),u.x), mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),u.x), u.y); }
float fbm(vec2 p){ float v=0.0; float a=0.5; for(int i=0; i < 4; i++){ v+=a*noise(p); p=p*2.02+vec2(1.7,9.2); a*=0.5; } return v; }
void main(){
  vec2 uv=vUv; float aspect=uResolution.x/max(uResolution.y,1.0);
  vec2 p=vec2((uv.x-0.5)*aspect, uv.y-0.5);
  vec2 n=p*max(1.0, 0.8/aspect);
  float t=uTime*0.075;
  vec2 q=vec2(fbm(n*1.35+vec2(0.0,t)), fbm(n*1.35+vec2(5.2,-0.8*t)));
  vec2 r=vec2(fbm(n*1.55+2.3*q+vec2(1.7,9.2)+0.6*t), fbm(n*1.55+2.3*q+vec2(8.3,2.8)-0.5*t));
  float f=fbm(n*1.15+2.6*r);
  float band=smoothstep(0.25,0.85,f+0.22*sin(n.x*1.7+3.0*t+3.0*r.y));
  vec3 cream=vec3(0.985,0.953,0.890); vec3 apricot=vec3(0.937,0.698,0.498);
  vec3 ochre=vec3(0.839,0.561,0.235); vec3 persimmon=vec3(0.815,0.384,0.227); vec3 rust=vec3(0.612,0.231,0.106);
  vec3 col=mix(cream,apricot,smoothstep(0.12,0.55,f));
  col=mix(col,ochre,smoothstep(0.38,0.74,r.x)*0.85);
  col=mix(col,persimmon,smoothstep(0.42,0.85,band*r.y+0.2)*0.85);
  col=mix(col,rust,smoothstep(0.55,0.92,f*band)*0.6);
  vec2 e=vec2(p.x/max(0.5,0.34*aspect), p.y/0.34);
  float reading=1.0-smoothstep(0.42,1.18,length(e));
  col=mix(col,cream,reading*0.82);
  col=mix(col,cream,smoothstep(0.34,0.5,p.y)*0.5);
  col+=(hash(floor(uv*uResolution))-0.5)*0.03;
  gl_FragColor=vec4(col,1.0);
}`;
  // Keep "<" followed by a space in this file: DOMPurify (inside st.html) drops any
  // script whose text contains "<" directly followed by a word character, "/" or "!".
  // The field starts at a composed moment; reduced motion shows that same frame.
  const START_TIME = 18.0;
  const STATIC_TIME = START_TIME;

  function startShader() {
    const host = byId('heroShader');
    if (!host) return;
    const hero = host.parentElement;
    const canvas = document.createElement('canvas');
    let gl;
    try {
      gl = canvas.getContext('webgl', { antialias: false, alpha: false, depth: false, stencil: false,
        powerPreference: 'low-power', preserveDrawingBuffer: false });
    } catch (error) { gl = null; }
    if (!gl) { host.dataset.state = 'fallback'; return; }

    function compile(type, source) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || 'shader');
      return shader;
    }
    let program;
    try {
      program = gl.createProgram();
      gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('link');
    } catch (error) {
      host.dataset.state = 'fallback';
      const lose = gl.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
      return;
    }
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'aPosition');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const uTime = gl.getUniformLocation(program, 'uTime');
    const uResolution = gl.getUniformLocation(program, 'uResolution');
    canvas.setAttribute('aria-hidden', 'true');
    host.appendChild(canvas);

    let elapsed = START_TIME;
    let last = 0;
    let frame = 0;
    let onScreen = true;
    let failed = false;

    function resize() {
      const scale = window.innerWidth < 760 ? 0.75 : 1;
      const width = Math.max(1, Math.round(host.clientWidth * scale));
      const height = Math.max(1, Math.round(host.clientHeight * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width; canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    }
    function draw(time) {
      if (failed || gl.isContextLost()) return;
      resize();
      gl.uniform1f(uTime, time);
      gl.uniform2f(uResolution, canvas.width, canvas.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      host.dataset.frames = String((Number(host.dataset.frames) || 0) + 1);
    }
    function tick(now) {
      frame = 0;
      if (!page.isConnected) { destroy(); return; }
      if (!shouldRun()) { last = 0; synchronize(); return; }
      // Accumulate active time only, so hidden/offscreen periods never jump.
      if (last) elapsed += Math.min((now - last) / 1000, 0.05);
      last = now;
      draw(elapsed);
      frame = window.requestAnimationFrame(tick);
    }
    function shouldRun() { return !failed && !reducedQuery.matches && onScreen && !document.hidden; }
    function synchronize() {
      if (failed) return;
      if (reducedQuery.matches) {
        if (frame) window.cancelAnimationFrame(frame);
        frame = 0; last = 0;
        host.dataset.state = 'static';
        draw(STATIC_TIME);
        return;
      }
      if (shouldRun()) {
        host.dataset.state = 'running';
        if (!frame) frame = window.requestAnimationFrame(tick);
      } else {
        if (frame) window.cancelAnimationFrame(frame);
        frame = 0; last = 0;
        host.dataset.state = 'paused';
      }
    }
    function fail() {
      failed = true;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      canvas.remove();
      host.dataset.state = 'fallback';
    }
    listen(canvas, 'webglcontextlost', (event) => { event.preventDefault(); fail(); });
    listen(document, 'visibilitychange', synchronize);
    listen(window, 'resize', () => { if (host.dataset.state === 'static') draw(STATIC_TIME); });
    onQueryChange(reducedQuery, synchronize);
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; synchronize(); });
      observer.observe(hero);
      cleanups.push(() => observer.disconnect());
    }
    cleanups.push(() => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      failed = true;
      canvas.remove();
    });
    synchronize();
  }
  try { startShader(); } catch (error) {
    const host = byId('heroShader');
    if (host) { host.dataset.state = 'fallback'; host.querySelectorAll('canvas').forEach((c) => c.remove()); }
  }

  // --- Restrained reveals and the workflow thread (CSS transitions own the motion) ---
  const revealTargets = Array.from(page.querySelectorAll('[data-reveal]'));
  const workflowBody = page.querySelector('.workflow-body');
  // One SVG path threads the six steps; CSS owns its stroke-dashoffset transition.
  if (workflowBody && !workflowBody.querySelector('.workflow-thread')) {
    const thread = svgElement('svg', { class: 'workflow-thread', viewBox: '0 0 2 100',
      preserveAspectRatio: 'none', focusable: 'false', 'aria-hidden': 'true' });
    thread.append(svgElement('path', { class: 'thread-draw', id: 'workflowThread', d: 'M1 0V100',
      pathLength: '1' }));
    workflowBody.prepend(thread);
    const fitThread = () => {
      const steps = workflowBody.querySelectorAll('.step-number');
      if (steps.length < 2) return;
      const origin = workflowBody.getBoundingClientRect().top;
      const first = steps[0].getBoundingClientRect();
      const last = steps[steps.length - 1].getBoundingClientRect();
      const top = first.top + first.height / 2 - origin;
      workflowBody.style.setProperty('--thread-top', `${top}px`);
      workflowBody.style.setProperty('--thread-height', `${Math.max(0, last.top + last.height / 2 - origin - top)}px`);
    };
    fitThread();
    if ('ResizeObserver' in window) {
      const sizer = new ResizeObserver(fitThread);
      sizer.observe(workflowBody);
      cleanups.push(() => sizer.disconnect());
    }
  }
  let revealObserver;
  function setupReveal() {
    if (revealObserver) { revealObserver.disconnect(); revealObserver = undefined; }
    if (reducedQuery.matches || !('IntersectionObserver' in window)) {
      page.classList.remove('reveal-ready', 'thread-ready');
      revealTargets.forEach((target) => target.classList.add('is-visible'));
      if (workflowBody) workflowBody.classList.add('is-drawn');
      return;
    }
    revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add(entry.target === workflowBody ? 'is-drawn' : 'is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.05 });
    revealTargets.forEach((target) => { if (!target.classList.contains('is-visible')) revealObserver.observe(target); });
    if (workflowBody && !workflowBody.classList.contains('is-drawn')) revealObserver.observe(workflowBody);
    page.classList.add('reveal-ready', 'thread-ready');
  }
  setupReveal();
  onQueryChange(reducedQuery, setupReveal);
  cleanups.push(() => { if (revealObserver) revealObserver.disconnect(); });

  // --- Cursor companion: desktop fine pointers only, never with reduced motion ---
  const ring = byId('deskCursor');
  let cursorFrame = 0;
  let cursorEnabled = false;
  const target = { x: 0, y: 0 };
  const current = { x: 0, y: 0 };
  function cursorLoop() {
    cursorFrame = 0;
    current.x += (target.x - current.x) * 0.22;
    current.y += (target.y - current.y) * 0.22;
    ring.style.transform = `translate3d(${current.x}px, ${current.y}px, 0)`;
    if (Math.abs(target.x - current.x) > 0.3 || Math.abs(target.y - current.y) > 0.3) {
      cursorFrame = window.requestAnimationFrame(cursorLoop);
    }
  }
  function onPointerMove(event) {
    if (!cursorEnabled || event.pointerType !== 'mouse') return;
    if (!ring.classList.contains('is-visible')) {
      current.x = event.clientX; current.y = event.clientY;
      ring.classList.add('is-visible');
    }
    target.x = event.clientX; target.y = event.clientY;
    const interactive = event.target instanceof Element && event.target.closest('a, button, select, label, input');
    ring.classList.toggle('is-active', Boolean(interactive));
    ring.classList.toggle('is-dark', Boolean(event.target instanceof Element && event.target.closest('.closing-cta, .preview-bar')));
    if (!cursorFrame) cursorFrame = window.requestAnimationFrame(cursorLoop);
  }
  function hideRing() { if (ring) ring.classList.remove('is-visible', 'is-active'); }
  function syncCursor() {
    cursorEnabled = Boolean(ring) && finePointerQuery.matches && !reducedQuery.matches;
    if (!cursorEnabled) {
      if (cursorFrame) window.cancelAnimationFrame(cursorFrame);
      cursorFrame = 0;
      hideRing();
    }
  }
  if (ring) {
    listen(page, 'pointermove', onPointerMove, { passive: true });
    listen(page, 'pointerleave', hideRing);
    listen(document, 'visibilitychange', () => { if (document.hidden) hideRing(); });
    onQueryChange(finePointerQuery, syncCursor);
    onQueryChange(reducedQuery, syncCursor);
    cleanups.push(() => { if (cursorFrame) window.cancelAnimationFrame(cursorFrame); hideRing(); });
    syncCursor();
  }

  function destroy() {
    while (cleanups.length) {
      try { cleanups.pop()(); } catch (error) { /* keep tearing down */ }
    }
    if (window.__inboxlearnLanding && window.__inboxlearnLanding.destroy === destroy) delete window.__inboxlearnLanding;
  }
  window.__inboxlearnLanding = { destroy };
})();
