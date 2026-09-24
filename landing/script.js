/**
 * InboxLearn — Newsprint Intelligence Landing Page Interactions
 * Pure vanilla JavaScript: Accessible, zero dependencies, lightweight.
 */

(function () {
  'use strict';

  // --- Real-world synthetic demo email fixtures ---
  const DEMO_EMAILS = [
    {
      id: 1,
      sender: "feedback-careers@example.test",
      date: "Today, 09:14 AM",
      subject: "Interview moved to Tuesday",
      snippet: "The hiring team moved your software interview to Tuesday morning…",
      body: "Hello,\n\nThe engineering hiring team has rescheduled your technical interview to Tuesday at 10:00 AM Eastern. Please confirm your availability or propose an alternative window via the applicant portal.\n\nBest regards,\nTalent Acquisition Team",
      predCategory: "job opportunities",
      predPriority: "high",
      confidence: "0.68",
      needsReview: true,
      reason: "Below threshold (0.68 < 0.70 category confidence)",
      modelVersion: "v1.0.4-active (Seed baseline)",
      format: "RFC 822 (.eml)"
    },
    {
      id: 2,
      sender: "feedback-billing@example.test",
      date: "Yesterday, 04:32 PM",
      subject: "Rent invoice available",
      snippet: "Your rent invoice is available with payment due on 5 October…",
      body: "Notice: Your monthly residential lease invoice for October has been generated and posted to your resident ledger.\n\nTotal Due: $1,450.00\nDue Date: October 5, 2026\nGrace period ends October 10.\n\nPlease remit payment through the resident portal.",
      predCategory: "bills",
      predPriority: "high",
      confidence: "0.74",
      needsReview: false,
      reason: "Above threshold (0.74 ≥ 0.70 category confidence)",
      modelVersion: "v1.0.4-active (Seed baseline)",
      format: "RFC 822 (.eml)"
    },
    {
      id: 3,
      sender: "feedback-campus@example.test",
      date: "2 days ago",
      subject: "Academic transcript request",
      snippet: "Please collect your academic transcript from the university office…",
      body: "Dear Student,\n\nYour official university transcript request has been printed and certified. You may collect your sealed document from Student Administrative Services, Hall B, Room 104 during regular office hours (9:00 AM – 4:00 PM).\n\nOffice of the Registrar",
      predCategory: "university",
      predPriority: "normal",
      confidence: "0.59",
      needsReview: true,
      reason: "Below threshold (0.59 < 0.70 category confidence)",
      modelVersion: "v1.0.4-active (Seed baseline)",
      format: "MBOX archive"
    }
  ];

  let currentEmailIndex = 0;
  let simulatedCorrectionsCount = 0;

  function makeElement(tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  }

  // DOM Elements
  const mobileToggle = document.getElementById('mobileNavToggle');
  const mobileDrawer = document.getElementById('mobileNavDrawer');
  const emailListEl = document.getElementById('emailList');
  const detailSubject = document.getElementById('detailSubject');
  const detailSender = document.getElementById('detailSender');
  const detailDate = document.getElementById('detailDate');
  const detailFormat = document.getElementById('detailFormat');
  const detailBody = document.getElementById('detailBody');
  const statPredCategory = document.getElementById('statPredCategory');
  const statPredPriority = document.getElementById('statPredPriority');
  const statConfidence = document.getElementById('statConfidence');
  const statReviewStatus = document.getElementById('statReviewStatus');
  const statModelVersion = document.getElementById('statModelVersion');
  const formCorrectionCategory = document.getElementById('correctionCategory');
  const formCorrectionPriority = document.getElementById('correctionPriority');
  const btnSaveCorrection = document.getElementById('btnSaveCorrection');
  const consoleStatusMsg = document.getElementById('consoleStatusMsg');
  const ledgerCounter = document.getElementById('ledgerCounter');
  const copyCmdBtn = document.getElementById('copyCmdBtn');

  // --- Mobile Navigation ---
  if (mobileToggle && mobileDrawer) {
    mobileToggle.addEventListener('click', function () {
      const isExpanded = mobileToggle.getAttribute('aria-expanded') === 'true';
      mobileToggle.setAttribute('aria-expanded', !isExpanded);
      mobileDrawer.classList.toggle('is-open');
    });

    // Close on navigation link click
    const drawerLinks = mobileDrawer.querySelectorAll('a');
    drawerLinks.forEach(link => {
      link.addEventListener('click', () => {
        mobileToggle.setAttribute('aria-expanded', 'false');
        mobileDrawer.classList.remove('is-open');
      });
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && mobileDrawer.classList.contains('is-open')) {
        mobileToggle.setAttribute('aria-expanded', 'false');
        mobileDrawer.classList.remove('is-open');
        mobileToggle.focus();
      }
    });
  }

  // --- Render Email Detail ---
  function renderEmail(index) {
    currentEmailIndex = index;
    const email = DEMO_EMAILS[index];
    if (!email) return;

    // Update left list active states
    if (emailListEl) {
      const buttons = emailListEl.querySelectorAll('.email-item-btn');
      buttons.forEach((btn, idx) => {
        btn.classList.toggle('is-active', idx === index);
        btn.setAttribute('aria-selected', idx === index ? 'true' : 'false');
      });
    }

    // Update message details
    if (detailSubject) detailSubject.textContent = email.subject;
    if (detailSender) detailSender.textContent = email.sender;
    if (detailDate) detailDate.textContent = email.date;
    if (detailFormat) detailFormat.textContent = email.format;
    if (detailBody) detailBody.textContent = email.body;

    // Update prediction stats
    if (statPredCategory) statPredCategory.textContent = email.predCategory;
    if (statPredPriority) statPredPriority.textContent = email.predPriority;
    if (statConfidence) {
      statConfidence.replaceChildren(
        document.createTextNode(`${email.confidence} `),
        makeElement('span', 'uncalibrated-notice', '(Uncalibrated raw sigmoid estimate)')
      );
    }

    if (statReviewStatus) {
      const badge = makeElement('span', email.needsReview ? 'badge badge-accent' : 'badge badge-ink',
        email.needsReview ? 'Needs Review' : 'Confident');
      const reason = makeElement('small', '', email.reason);
      reason.style.cssText = 'display:block;margin-top:2px;color:var(--np-secondary)';
      statReviewStatus.replaceChildren(badge, reason);
    }

    if (statModelVersion) {
      statModelVersion.textContent = email.modelVersion;
    }

    // Pre-populate correction form with current prediction for easy adjustment
    if (formCorrectionCategory) formCorrectionCategory.value = email.predCategory;
    if (formCorrectionPriority) formCorrectionPriority.value = email.predPriority;

    if (consoleStatusMsg) {
      consoleStatusMsg.textContent = `Previewing synthetic email #${email.id}. Predictions are illustrative; nothing is saved or trained.`;
    }
  }

  // --- Populate Email List in Mockup ---
  if (emailListEl) {
    emailListEl.replaceChildren();
    DEMO_EMAILS.forEach((email, idx) => {
      const li = document.createElement('li');
      const button = makeElement('button', `email-item-btn ${idx === 0 ? 'is-active' : ''}`);
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', idx === 0 ? 'true' : 'false');
      const header = makeElement('div', 'email-item-header');
      header.append(makeElement('span', '', `#0${email.id}`), makeElement('span', '', email.date));
      const tags = makeElement('div');
      tags.append(makeElement('span', 'email-item-tag', email.predCategory));
      if (email.needsReview) {
        const badge = makeElement('span', 'badge badge-accent', 'Review');
        badge.style.cssText = 'font-size:0.6rem;padding:1px 4px;';
        tags.append(badge);
      }
      button.append(header, makeElement('div', 'email-item-subject', email.subject),
        makeElement('div', 'email-item-snippet', email.snippet), tags);
      button.addEventListener('click', () => {
        renderEmail(idx);
      });
      li.append(button);
      emailListEl.appendChild(li);
    });
    // Initial render
    renderEmail(0);
  }

  // --- Simulate Human Correction in Demo ---
  if (btnSaveCorrection) {
    btnSaveCorrection.addEventListener('click', function (e) {
      e.preventDefault();
      const email = DEMO_EMAILS[currentEmailIndex];
      const selectedCat = formCorrectionCategory ? formCorrectionCategory.value : email.predCategory;
      const selectedPri = formCorrectionPriority ? formCorrectionPriority.value : email.predPriority;

      simulatedCorrectionsCount++;
      if (ledgerCounter) {
        ledgerCounter.textContent = simulatedCorrectionsCount;
      }

      if (consoleStatusMsg) {
        const label = makeElement('strong', '', '[PREVIEW ONLY]');
        label.style.color = 'var(--np-accent)';
        consoleStatusMsg.replaceChildren(label, document.createTextNode(
          ` Simulated correction for #${email.id} (${selectedCat}, ${selectedPri}). Nothing was saved to SQLite or queued for training. Open InboxLearn to save real feedback.`
        ));
      }

      // Briefly animate button
      const originalContent = [...btnSaveCorrection.childNodes];
      btnSaveCorrection.textContent = `✓ Previewed #${email.id}`;
      btnSaveCorrection.disabled = true;

      setTimeout(() => {
        btnSaveCorrection.replaceChildren(...originalContent);
        btnSaveCorrection.disabled = false;
        // Advance to next email if available
        const nextIndex = (currentEmailIndex + 1) % DEMO_EMAILS.length;
        renderEmail(nextIndex);
      }, 1200);
    });
  }

  // --- Copy Command Snippet ---
  if (copyCmdBtn) {
    copyCmdBtn.addEventListener('click', function () {
      const textToCopy = "streamlit run app.py";
      navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = copyCmdBtn.textContent;
        copyCmdBtn.textContent = "COPIED!";
        setTimeout(() => {
          copyCmdBtn.textContent = originalText;
        }, 1800);
      }).catch(err => {
        console.warn("Clipboard access denied:", err);
      });
    });
  }

})();
