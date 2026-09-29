import React, { lazy, Suspense, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight } from 'lucide-react';

const HeroScene = lazy(() => import('./components/HeroScene').then(({ HeroScene: Scene }) => ({ default: Scene })));

/** The public introduction stays separate from the operational /app workspace. */
export function LandingPage() {
  const pageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const page = pageRef.current;
    if (!page) return;

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const revealTargets = page.querySelectorAll<HTMLElement>('[data-reveal]');
    let observer: IntersectionObserver | undefined;

    const revealAll = () => {
      observer?.disconnect();
      revealTargets.forEach((target) => target.classList.add('is-visible'));
      page.classList.remove('landing-motion-ready');
    };
    const observe = () => {
      if (motionPreference.matches || !('IntersectionObserver' in window)) {
        revealAll();
        return;
      }

      page.classList.add('landing-motion-ready');
      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer?.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
      revealTargets.forEach((target) => observer?.observe(target));
    };
    const onMotionChange = () => motionPreference.matches ? revealAll() : observe();

    observe();
    if (motionPreference.addEventListener) motionPreference.addEventListener('change', onMotionChange);
    else motionPreference.addListener(onMotionChange);
    return () => {
      observer?.disconnect();
      if (motionPreference.removeEventListener) motionPreference.removeEventListener('change', onMotionChange);
      else motionPreference.removeListener(onMotionChange);
    };
  }, []);

  return (
    <div ref={pageRef} className="landing-page min-h-screen overflow-x-hidden bg-paper text-ink font-sans selection:bg-rust-tint selection:text-rust">
      <a className="landing-skip-link" href="#main-content">Skip to content</a>

      <header className="landing-header">
        <Link to="/" aria-label="InboxLearn home" className="font-serif text-xl font-semibold tracking-tight text-ink">
          InboxLearn
        </Link>
        <Link
          to="/app"
          className="landing-nav-link focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rust"
        >
          Open workspace <span aria-hidden="true">↗</span>
        </Link>
      </header>

      <main id="main-content">
        <section className="landing-hero" aria-labelledby="landing-title">
          <Suspense fallback={<div className="landing-hero-scene hero-gradient-fallback" aria-hidden="true" />}>
            <HeroScene className="landing-hero-scene" />
          </Suspense>
          <div className="landing-hero-shade" aria-hidden="true" />
          <div className="landing-hero-copy">
            <p className="landing-kicker landing-hero-enter landing-hero-enter-1">A local system for thoughtful email triage</p>
            <h1 id="landing-title" className="font-serif landing-hero-enter landing-hero-enter-2">
              Better decisions,<br /><em>learned together.</em>
            </h1>
            <p className="landing-deck landing-hero-enter landing-hero-enter-3">
              InboxLearn brings human review and model improvement into one private, local workflow.
            </p>
          </div>
          <a href="#how-it-works" className="landing-scroll-cue" aria-label="Scroll to learn how InboxLearn works">
            <span>Scroll to explore</span><ArrowDown size={15} aria-hidden="true" />
          </a>
        </section>

        <section id="how-it-works" className="landing-section landing-intro" data-reveal>
          <div className="landing-section-label">01 <span>THE PRACTICE</span></div>
          <div className="landing-section-body">
            <h2 className="font-serif">A useful prediction<br />knows when to ask.</h2>
            <p>
              InboxLearn reads .eml, .mbox, or CSV email files (or the local demo set), then suggests a
              category and priority. Either prediction can be routed for review when it falls below
              its configured confidence threshold. A person can confirm or change the labels; saved
              corrections can train a candidate that is compared and evaluated before activation.
            </p>
            <Link to="/app" className="landing-text-link">
              Explore the workspace <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </section>

        <section className="landing-process" aria-labelledby="process-title" data-reveal>
          <div className="landing-process-heading">
            <div className="landing-section-label">A LOOP WITH A HUMAN IN IT</div>
            <h2 id="process-title" className="font-serif">From message to better judgment.</h2>
            <p>The model makes a suggestion. The review desk decides what happens next.</p>
          </div>
          <div className="workflow-figure" role="img" aria-label="Workflow: email intake, category and priority suggestions, human review for uncertain predictions, then feedback for candidate training and evaluation.">
            <div className="workflow-track" aria-hidden="true"><span className="workflow-track-line" /><span className="workflow-track-pulse" /></div>
            <div className="workflow-nodes" aria-hidden="true">
              <div className="workflow-node workflow-node-mail"><span className="workflow-node-index">01 / INTAKE</span><div className="workflow-mail-icon"><span /><span /><span /></div><strong>Email arrives</strong><small>Imported message</small></div>
              <div className="workflow-node workflow-node-model"><span className="workflow-node-index">02 / SUGGEST</span><div className="workflow-predictions"><span>category</span><b>bills</b><span>priority</span><b>normal</b></div><strong>Model estimates</strong><small>Confidence checked</small></div>
              <div className="workflow-node workflow-node-human"><span className="workflow-node-index">03 / REVIEW</span><div className="workflow-review-mark"><span>?</span><i>human review</i></div><strong>A person confirms</strong><small>Correct labels if needed</small></div>
              <div className="workflow-node workflow-node-learn"><span className="workflow-node-index">04 / IMPROVE</span><div className="workflow-version-mark"><span>v1</span><b>→</b><span>v2</span></div><strong>Candidate is checked</strong><small>Evaluate before activation</small></div>
            </div>
            <div className="workflow-return" aria-hidden="true"><span>Saved corrections inform a candidate model</span></div>
          </div>
        </section>

        <section className="landing-section landing-workflow" aria-labelledby="workflow-title" data-reveal>
          <div className="landing-section-label">02 <span>THE WORKFLOW</span></div>
          <div className="landing-section-body">
            <h2 id="workflow-title" className="font-serif">Review. Compare. Promote.</h2>
            <ol className="landing-steps">
              <li><span>01</span><div><h3>Bring email into the inbox</h3><p>Import an .eml, .mbox, or CSV file, or use the bundled demo set. InboxLearn predicts a category and priority and shows the confidence behind each suggestion.</p></div></li>
              <li><span>02</span><div><h3>Review and correct</h3><p>Low-confidence messages are easy to find. Inspect the original email and rationale, then save the category and priority you confirm.</p></div></li>
              <li><span>03</span><div><h3>Compare before changing models</h3><p>Prepare a candidate from saved corrections, compare its inbox predictions, and evaluate it on a selected held-out dataset before activation. Older versions can be restored.</p></div></li>
            </ol>
          </div>
        </section>

        <section className="landing-section landing-principles" aria-labelledby="principles-title" data-reveal>
          <div className="landing-section-label">03 <span>BUILT WITH CARE</span></div>
          <div className="landing-section-body">
            <h2 id="principles-title" className="font-serif">Small, explicit guarantees.</h2>
            <div className="landing-principle-list">
              <p><strong>Local by design.</strong> The web client talks to the local InboxLearn API; model and workflow data are stored in SQLite.</p>
              <p><strong>Fixed feature space.</strong> Stateless 4,096-dimensional hashing keeps feature dimensions stable across model versions.</p>
              <p><strong>Safer model files.</strong> The IBL1 format validates model arrays and checksums; normal loading does not deserialize Python pickle.</p>
            </div>
          </div>
        </section>

        <section className="landing-enter" aria-labelledby="enter-title" data-reveal>
          <p className="landing-kicker">Your review desk is ready</p>
          <h2 id="enter-title" className="font-serif">See the whole learning loop.</h2>
          <Link to="/app" className="landing-enter-link">
            Enter InboxLearn <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <span className="font-serif">InboxLearn</span>
        <span>Local email triage and model lifecycle</span>
        <Link to="/app">Open workspace <span aria-hidden="true">↗</span></Link>
      </footer>
    </div>
  );
}

export default LandingPage;
