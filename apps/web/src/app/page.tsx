import Link from "next/link";

import { GravityMark } from "@/components/ui";

import { LaunchOffer } from "./launch-offer";
import styles from "./landing.module.css";

const CAPABILITIES = [
  { number: "01", title: "Keep your work together", description: "Projects, tasks, and your catalogue live in one workspace, so the details stay close to the big picture." },
  { number: "02", title: "Plan the next release", description: "Turn a release into a timeline of work, with budgets and marketing plans alongside it." },
  { number: "03", title: "See what needs attention", description: "A focused dashboard and calendar help you keep moving without losing track of what comes next." },
];

export default function Home() {
  return (
    <main className={styles.page}>
      <a className={styles.skipLink} href="#main-content">Skip to content</a>
      <header className={styles.header}>
        <Link className={styles.brand} href="/" aria-label="GravityOS home">
          <GravityMark size={30} /><span>GravityOS</span>
        </Link>
        <nav className={styles.navigation} aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#features">Features</a>
          <a href="#plans">Plans</a>
        </nav>
        <div className={styles.headerActions}>
          <Link className={styles.loginLink} href="/login">Log in</Link>
          <Link className={styles.smallButton} href="/signup">Get started <span aria-hidden="true">↗</span></Link>
        </div>
      </header>

      <section className={styles.hero} id="main-content" aria-labelledby="hero-title">
        <div className={styles.heroCopy}>
          <p className={styles.kicker}><span className={styles.kickerDot} /> YOUR CREATIVE WORK, IN ONE PLACE</p>
          <h1 id="hero-title">Make room for <span>your next big thing.</span></h1>
          <p className={styles.lead}>From the first idea to the next release, GravityOS gives your projects, catalogue, plans, and daily work a place to move together.</p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryButton} href="/signup">Create your free account <span aria-hidden="true">↗</span></Link>
            <a className={styles.secondaryButton} href="#how-it-works">See how it works <span aria-hidden="true">↓</span></a>
          </div>
          <p className={styles.heroNote}>Start on Free · No card needed to get started</p>
        </div>
        <div className={styles.previewFrame} aria-label="Illustrative preview of a GravityOS workspace">
          <div className={styles.previewTop}><span className={styles.previewDots} aria-hidden="true">● ● ●</span><span>MISSION CONTROL</span><span>◌</span></div>
          <div className={styles.previewBody}>
            <aside className={styles.previewSide} aria-hidden="true"><div className={styles.previewSymbol}>G</div><span className={styles.previewSideActive}>◈</span><span>▤</span><span>◷</span><span>▧</span></aside>
            <div className={styles.previewContent}>
              <div className={styles.previewIntro}><div><span className={styles.previewLabel}>YOUR WORKSPACE</span><h2>Good things are in motion.</h2></div><span className={styles.previewDate}>A LOOK INSIDE</span></div>
              <div className={styles.previewGrid}>
                <div className={styles.previewFeature}><span className={styles.previewLabel}>CURRENT PROJECT</span><strong>Next release</strong><p>Give every step a place to land.</p><div className={styles.progressTrack}><div /></div><span className={styles.progressCaption}>Your plan, coming together</span></div>
                <div className={styles.previewStat}><span className={styles.previewLabel}>UP NEXT</span><strong>3 priorities</strong><div className={styles.previewTask}><span>✓</span> Set the direction</div><div className={styles.previewTask}><span>○</span> Map the rollout</div><div className={styles.previewTask}><span>○</span> Share the work</div></div>
              </div>
              <div className={styles.previewBottom}><span>PROJECTS</span><span>CATALOGUE</span><span>RELEASES</span><span>CALENDAR</span></div>
            </div>
          </div>
          <span className={styles.previewCaption}>An illustrative workspace preview</span>
        </div>
      </section>

      <LaunchOffer />

      <section id="how-it-works" className={styles.section} aria-labelledby="workflow-title">
        <div className={styles.sectionHeading}><p className={styles.kicker}>A CLEARER WAY TO MOVE</p><h2 id="workflow-title">Your ideas deserve more than scattered tabs.</h2><p>Bring the work behind your creative career into one dependable rhythm.</p></div>
        <div className={styles.stepGrid}>
          <div><span>01 / ORGANIZE</span><h3>Start with the work</h3><p>Create a project and bring the tasks, notes, and assets around it into focus.</p></div>
          <div><span>02 / PLAN</span><h3>See the path ahead</h3><p>Build your release plan, make space for your budget, and map the moments that matter.</p></div>
          <div><span>03 / KEEP GOING</span><h3>Find your next move</h3><p>Use your dashboard and calendar to stay connected to what needs you today.</p></div>
        </div>
      </section>

      <section id="features" className={styles.section} aria-labelledby="feature-title">
        <div className={styles.sectionHeading}><p className={styles.kicker}>BUILT FOR THE WHOLE JOURNEY</p><h2 id="feature-title">Less switching. More making.</h2></div>
        <div className={styles.featureGrid}>{CAPABILITIES.map((feature) => <article className={styles.featureCard} key={feature.number}><span>{feature.number}</span><h3>{feature.title}</h3><p>{feature.description}</p></article>)}</div>
      </section>

      <section id="plans" className={styles.section} aria-labelledby="plans-title">
        <div className={styles.sectionHeading}><p className={styles.kicker}>ROOM TO GROW</p><h2 id="plans-title">Begin where you are.</h2><p>Start free and explore more when a trial is available to your account.</p></div>
        <div className={styles.planGrid}>
          <div className={styles.planCard}><p className={styles.planName}>FREE</p><h3>Get your ideas moving.</h3><p>One active project, 25 catalogue items, tasks, calendar, and a dashboard to get started.</p><strong>₦0 <span>/ forever</span></strong><Link className={styles.secondaryButton} href="/signup">Start free <span aria-hidden="true">↗</span></Link></div>
          <div className={`${styles.planCard} ${styles.planCardPro}`}><p className={styles.planName}>PRO</p><h3>Give every plan more room.</h3><p>Unlimited projects and catalogue, plus release, budget, and marketing planning.</p><span className={styles.planDetail}>A seven-day trial is available to eligible accounts during the launch window. No payment card or automatic charge.</span><Link className={styles.primaryButton} href="/signup">Explore GravityOS <span aria-hidden="true">↗</span></Link></div>
        </div>
        <p className={styles.teamNote}>Working with a team? Shared workspaces and team tools are part of GravityOS too. Payment checkout is not available yet.</p>
      </section>

      <section className={styles.finalCta}><p className={styles.kicker}>READY WHEN YOU ARE</p><h2>Make the space to do your best work.</h2><p>Your next chapter starts with one place to plan it.</p><Link className={styles.primaryButton} href="/signup">Get started for free <span aria-hidden="true">↗</span></Link></section>
      <footer className={styles.footer}><Link className={styles.brand} href="/"><GravityMark size={23} /><span>GravityOS</span></Link><span>Build with intention. Move with momentum.</span><Link href="/login">Log in</Link></footer>
    </main>
  );
}
