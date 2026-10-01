import React, { lazy, Suspense, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, Mail } from 'lucide-react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { LandingReviewPreview } from './components/LandingReviewPreview';
import { LandingWorkflow } from './components/LandingWorkflow';
import { IntakeIllustration } from './components/IntakeIllustration';
import { ModelDecisionDemo } from './components/ModelDecisionDemo';
import './redesign.css';

const HeroScene = lazy(() => import('./components/HeroScene').then(({ HeroScene: Scene }) => ({ default: Scene })));

/** The public introduction stays separate from the operational /app workspace. */
export function LandingPage() {
  const pageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const page = pageRef.current;
    if (!page) return;

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const played = new WeakSet<HTMLElement>();
    let context: gsap.Context | undefined;
    const synchronize = () => {
      context?.revert();
      context = undefined;
      if (motionPreference.matches || document.hidden) return;
      try {
        gsap.registerPlugin(ScrollTrigger);
        context = gsap.context(() => {}, page);
        context.add((owned) => {
          gsap.fromTo('.story-track-fill', { scaleX: 0 }, { scaleX: 1, ease: 'none', scrollTrigger: { trigger: '.landing-process', start: 'top 85%', end: 'bottom 60%', scrub: .4 } });
          page.querySelectorAll<HTMLElement>('[data-reveal]').forEach((target) => {
            if (played.has(target)) return;
            // Only animate at entry; no initialization step hides static content.
            owned.add(() => {
              ScrollTrigger.create({ trigger: target, start: 'top 88%', once: true,
                onEnter: () => owned.add(() => {
                  played.add(target);
                  gsap.fromTo(target, { opacity: .7, y: 18 }, { opacity: 1, y: 0, duration: .65, ease: 'power2.out' });
                }),
              });
            });
          });
        });
      } catch { context?.revert(); }
    };
    synchronize();
    motionPreference.addEventListener('change', synchronize);
    document.addEventListener('visibilitychange', synchronize);
    return () => {
      context?.revert();
      motionPreference.removeEventListener('change', synchronize);
      document.removeEventListener('visibilitychange', synchronize);
    };
  }, []);

  return (
    <div ref={pageRef} className="landing-page min-h-screen overflow-x-hidden bg-paper text-ink font-sans selection:bg-rust-tint selection:text-rust">
      <a className="landing-skip-link" href="#main-content">Skip to content</a>

      <header className="landing-header">
        <Link to="/" aria-label="InboxLearn home" className="landing-wordmark"><Mail size={24} strokeWidth={1.5} aria-hidden="true" />InboxLearn<span className="brand-period">.</span></Link>
        <nav aria-label="Main navigation"><a href="#how-it-works" className="landing-about-link">How it works</a><Link to="/app" className="landing-nav-link">Open workspace <ArrowRight size={16} aria-hidden="true" /></Link></nav>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section className="landing-hero" aria-labelledby="landing-title">
          <Suspense fallback={<div className="landing-hero-scene hero-gradient-fallback" aria-hidden="true" />}>
            <HeroScene className="landing-hero-scene" />
          </Suspense>
          <div className="landing-hero-copy">
            <p className="landing-kicker landing-hero-enter landing-hero-enter-1">A little intelligence. A human touch.</p>
            <h1 id="landing-title" className="font-serif landing-hero-enter landing-hero-enter-2">
              An inbox that learns<br /><em>from you.</em>
            </h1>
            <p className="landing-deck landing-hero-enter landing-hero-enter-3">
              Sort the everyday. Give the uncertain a second look.
              Turn your corrections into a model you can put to the test.
            </p>
            <Link to="/app" className="landing-hero-cta landing-hero-enter landing-hero-enter-4">
              Open your review desk <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
          <a href="#how-it-works" className="landing-scroll-cue" aria-label="Scroll to learn how InboxLearn works">
            <span>A closer look</span><ArrowDown size={15} aria-hidden="true" />
          </a>
        </section>

        <section id="how-it-works" className="story-intake" aria-labelledby="intake-title">
          <div className="story-intake-copy" data-reveal>
            <div className="landing-section-label">01 / A PLACE FOR EVERY MESSAGE</div>
            <h2 id="intake-title">Less sorting.<br /><em>More knowing.</em></h2>
            <p>An invoice. An invitation. Something that can wait. Bring in your email, and InboxLearn suggests a category and priority for each message.</p>
            <p>Confidence tells you where to look closer. When a suggestion is uncertain, it comes to you for a second opinion.</p>
            <div className="import-formats" aria-label="Supported email formats"><span>.eml <small>One email</small></span><span>.mbox <small>A mailbox</small></span><span>.csv <small>A collection</small></span></div>
            <Link to="/app" className="landing-text-link">Start with your email, or try the demo <ArrowRight size={16} aria-hidden="true" /></Link>
          </div>
          <IntakeIllustration />
        </section>

        <section id="review-preview" className="landing-review-section" aria-labelledby="review-title">
          <div className="landing-review-heading" data-reveal>
            <div className="landing-section-label">02 / YOUR JUDGMENT MATTERS</div>
            <div><h2 id="review-title" className="font-serif">You know the context.<br /><em>Teach it the difference.</em></h2>
            <p>An invoice reminder isn’t a promotion. A delivery problem can’t always wait. Try a correction below and see how your judgment becomes a useful label.</p></div>
          </div>
          <LandingReviewPreview />
          <p className="preview-workspace-link">Ready for the real workflow? <Link to="/app" className="landing-text-link">Open the review desk <ArrowRight size={16} aria-hidden="true" /></Link></p>
        </section>

        <section className="landing-process" aria-labelledby="compare-title">
          <div className="landing-process-heading" data-reveal>
            <div className="landing-section-label">03 / PREPARE &amp; COMPARE</div>
            <h2 id="compare-title" className="font-serif">Small corrections.<br /><em>A considered next step.</em></h2>
            <p>Your saved feedback becomes training material for a candidate. Compare its predictions with the current model. See what changes before anything goes live.</p>
          </div>
          <div className="story-track" aria-hidden="true"><div className="story-track-fill" /></div>
          <LandingWorkflow />
        </section>

        <section className="story-decision" aria-labelledby="evaluation-title">
          <div className="story-decision-copy" data-reveal>
            <div className="landing-section-label">04 / EVIDENCE BEFORE ACTIVATION</div>
            <h2 id="evaluation-title">Better is something<br /><em>you check.</em></h2>
            <p>A new model deserves a separate test. Evaluate on held-out examples, inspect category and priority results, then choose whether to activate. The server checks eligibility.</p>
            <p>Evaluation is a prerequisite, never a promise of improvement. Preparing or evaluating a candidate leaves your active model in place.</p>
            <div className="rollback-note"><span>05 / A WAY BACK</span><h3>Change your mind.<br />Keep your learning.</h3><p>The version ledger keeps your model history. Restore an earlier version when you need to; your feedback stays with you.</p><Link to="/app" className="landing-text-link">Explore the workspace <ArrowRight size={16} aria-hidden="true" /></Link></div>
          </div>
          <ModelDecisionDemo />
        </section>

        <section className="landing-enter" aria-labelledby="enter-title" data-reveal>
          <p className="landing-kicker">Made for the messages that need you.</p>
          <h2 id="enter-title" className="font-serif">A clearer inbox.<br /><em>A little more you.</em></h2>
          <Link to="/app" className="landing-enter-link">
            Open your review desk <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <span className="font-serif">InboxLearn</span>
        <span>Your email. Your judgment. Your next model.</span>
        <Link to="/app">Open workspace <span aria-hidden="true">↗</span></Link>
      </footer>
    </div>
  );
}

export default LandingPage;
