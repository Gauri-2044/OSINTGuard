import { Shield, Rocket, MessageSquare, Briefcase, Brain, Lock, Eye, Zap, ChevronRight, Activity, Sparkles } from 'lucide-react';

const StatBadge = ({ value, label }) => (
  <div className="flex flex-col items-center glass-card rounded-2xl px-6 py-4 min-w-[120px] border border-white/10 hover:border-cyan-500/40 transition-all duration-300">
    <span className="text-2xl sm:text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-indigo-400 font-mono tracking-tight">{value}</span>
    <span className="text-xs text-slate-400 mt-1 font-medium tracking-wide">{label}</span>
  </div>
);

const UseCase = ({ icon: Icon, platform, title, description }) => (
  <div className="group relative glass-card glass-card-hover rounded-3xl p-7 border border-white/10 overflow-hidden">
    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl group-hover:bg-cyan-500/20 transition-all duration-500 pointer-events-none" />
    <div className="relative z-10">
      <div className="flex items-center justify-between mb-5">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/10 border border-white/15 flex items-center justify-center group-hover:scale-105 transition-transform duration-300 shadow-lg shadow-indigo-950/30">
          <Icon className="w-6 h-6 text-cyan-400" />
        </div>
        <span className="text-[11px] font-mono text-cyan-300/90 font-semibold px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 uppercase tracking-wider">
          {platform}
        </span>
      </div>
      <h3 className="text-white font-bold text-xl mb-2.5 tracking-tight">{title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed font-normal">{description}</p>
      <div className="mt-6 flex items-center gap-2 text-cyan-400 text-sm font-semibold group-hover:text-cyan-300 transition-colors">
        <span>Explore Shield</span>
        <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
      </div>
    </div>
  </div>
);

const ThreatTicker = () => {
  const threats = [
    'LOCATION LEAK DETECTED', 'DEVICE INFO EXPOSED', 'NETWORK FINGERPRINT',
    'ROUTINE PATTERN RISK', 'EMPLOYER DATA VISIBLE', 'TRAVEL SCHEDULE EXPOSED'
  ];
  return (
    <div className="overflow-hidden border-y border-white/10 py-3 bg-slate-950/60 backdrop-blur-md">
      <div className="flex gap-12 animate-[scroll_25s_linear_infinite] whitespace-nowrap">
        {[...threats, ...threats].map((t, i) => (
          <span key={i} className="text-xs font-mono text-slate-400 flex items-center gap-2.5 font-medium tracking-wider">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shadow-[0_0_8px_#f43f5e]" />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
};

/* ── Nexus AI Centerpiece Graphic ── */
const NexusAiHeroGraphic = () => (
  <div className="relative w-72 h-72 sm:w-80 sm:h-80 mx-auto my-6 flex items-center justify-center">
    {/* Outer glowing blur ring */}
    <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-indigo-600/30 via-purple-600/20 to-cyan-400/30 blur-3xl animate-pulse-slow" />
    
    {/* Outer orbit ring */}
    <div className="absolute inset-2 rounded-full border border-cyan-500/20 border-dashed animate-spin-slow" />
    
    {/* Secondary orbit ring */}
    <div className="absolute inset-8 rounded-full border border-indigo-400/30 border-t-cyan-400 animate-[spin_8s_linear_infinite_reverse]" />
    
    {/* Glass sphere shell matching Nexus AI hero orb */}
    <div className="relative w-48 h-48 sm:w-56 sm:h-56 rounded-full glass-card border border-white/20 flex flex-col items-center justify-center shadow-[0_0_50px_rgba(79,70,229,0.35)] overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-b from-cyan-500/10 via-indigo-600/20 to-purple-900/40" />
      
      {/* Dynamic light refraction reflection */}
      <div className="absolute -top-12 -left-12 w-32 h-32 bg-white/10 rounded-full blur-xl transform rotate-45" />
      
      {/* Central AI core logo badge */}
      <div className="relative z-10 w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center shadow-[0_0_30px_rgba(56,189,248,0.7)] group-hover:scale-110 transition-transform duration-500">
        <span className="text-3xl font-extrabold text-white tracking-tighter">AI</span>
      </div>

      <div className="relative z-10 mt-3 flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-900/80 border border-cyan-500/30">
        <Sparkles className="w-3 h-3 text-cyan-400 animate-spin" />
        <span className="text-[10px] font-mono text-cyan-300 font-semibold tracking-widest uppercase">OSINT Shield Active</span>
      </div>
    </div>
  </div>
);

export default function LandingPage({ onLaunch }) {
  return (
    <div className="min-h-screen bg-grid-pattern relative overflow-x-hidden bg-[#090d16] text-slate-100 font-sans">

      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-indigo-900/20 via-cyan-900/10 to-transparent blur-[140px] pointer-events-none" />

      {/* ── Top Bar Header (Nexus AI Pill Style) ── */}
      <header className="fixed top-4 left-0 right-0 z-50 px-4 sm:px-8">
        <div className="max-w-6xl mx-auto h-14 rounded-full glass-card px-6 flex items-center justify-between border border-white/15 shadow-2xl backdrop-blur-xl bg-slate-950/80">
          
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center shadow-[0_0_15px_rgba(56,189,248,0.5)]">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-extrabold text-base text-white tracking-tight">
              OSINT<span className="text-cyan-400">Guard</span>
            </span>
          </div>


          {/* Action */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-mono text-emerald-300 font-medium">SHIELD READY</span>
            </div>
            <button
              onClick={onLaunch}
              className="text-xs font-bold px-5 py-2 rounded-full text-white transition-all btn-primary shadow-lg"
            >
              Launch App
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="relative pt-36 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center relative z-10">

          {/* Eyebrow badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-6 border border-cyan-500/30 bg-cyan-500/10 backdrop-blur-md">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-xs font-mono text-cyan-300 tracking-widest uppercase font-semibold">AI-POWERED OSINT DEFENSE</span>
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-6xl font-extrabold leading-[1.1] tracking-tight mb-6 text-white">
            Share Your Ideas,
            <br />
            <span className="text-gradient">Not Your Secrets.</span>
          </h1>

          <p className="text-slate-300 text-base sm:text-lg max-w-2xl mx-auto leading-relaxed mb-8 font-normal">
            Paste your social media draft. Our AI scans for data leaks, location traces, and personal identifiers — then rewrites it, clean and safe.
          </p>

          {/* Nexus AI Orb Centerpiece Visual */}
          <NexusAiHeroGraphic />

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-6">
            <button
              onClick={onLaunch}
              className="flex items-center gap-3 px-8 py-4 rounded-full text-white font-bold text-sm transition-all btn-primary shadow-xl shadow-indigo-950/50 hover:scale-105"
            >
              <Rocket className="w-4 h-4" />
              Launch OSINT Scanner
            </button>
            <div className="flex items-center gap-2 text-slate-400 text-xs px-4 py-2 rounded-full bg-slate-900/60 border border-white/5">
              <Lock className="w-3.5 h-3.5 text-cyan-400" />
              <span>No data stored · 100% Client-Safe</span>
            </div>
          </div>

          {/* Stats Row */}
          <div className="mt-14 flex flex-wrap items-center justify-center gap-4">
            <StatBadge value="47+" label="Risk Categories" />
            <StatBadge value="< 1.8s" label="Analysis Time" />
            <StatBadge value="99.4%" label="Detection Rate" />
          </div>
        </div>
      </section>

      {/* Ticker */}
      <ThreatTicker />

      {/* ── Use Cases ── */}
      <section className="py-24 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-xs font-mono text-cyan-400 uppercase tracking-widest mb-2 font-bold">COVERAGE MATRIX</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">Every platform, every threat vector</h2>
            <p className="text-slate-400 mt-3 text-sm max-w-xl mx-auto leading-relaxed">From casual tweets to professional posts, our OSINT engine catches what you might miss.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <UseCase
              icon={MessageSquare}
              platform="Twitter / X"
              title="Stop casual oversharing"
              description="That quick tweet about your coffee spot? It just revealed your neighborhood, daily routine, and employer. We catch it before it goes live."
            />
            <UseCase
              icon={Briefcase}
              platform="LinkedIn"
              title="Protect professional data"
              description="Announcing a new project? Your post may expose client names, internal tools, unreleased products, and office locations. We sanitize it automatically."
            />
            <UseCase
              icon={Brain}
              platform="AI Prompts"
              title="Sanitize LLM inputs"
              description="Before pasting work context into ChatGPT or Claude, scan for embedded PII, trade secrets, and system info you didn't realize was there."
            />
          </div>
        </div>
      </section>

      {/* ── Process Steps ── */}
      <section className="py-20 px-6 border-t border-white/10 relative z-10 bg-slate-950/40 backdrop-blur-md">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-xs font-mono text-cyan-400 uppercase tracking-widest mb-2 font-bold">HOW IT WORKS</p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">Three steps to safer posts</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { step: '01', icon: Eye, label: 'Paste Draft', desc: 'Drop in your raw post, exactly as written.' },
              { step: '02', icon: Zap, label: 'AI Scans', desc: 'Our model maps every OSINT risk and attack vector.' },
              { step: '03', icon: Shield, label: 'Publish Safe', desc: 'Copy the clean rewrite. Zero secrets exposed.' },
            ].map(({ step, icon: Icon, label, desc }) => (
              <div key={step} className="flex flex-col items-center text-center group">
                <div className="relative mb-5">
                  <div className="w-16 h-16 rounded-2xl glass-card flex items-center justify-center border border-white/15 shadow-lg group-hover:border-cyan-500/40 transition-all duration-300">
                    <Icon className="w-7 h-7 text-cyan-400" />
                  </div>
                  <span className="absolute -top-2 -right-2 text-[11px] font-mono font-bold text-white px-2 py-0.5 rounded-full bg-gradient-to-r from-indigo-600 to-cyan-500 shadow-md">{step}</span>
                </div>
                <h3 className="text-white font-bold text-lg mb-1.5">{label}</h3>
                <p className="text-slate-400 text-xs leading-relaxed max-w-xs">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer CTA ── */}
      <section className="py-20 px-6 border-t border-white/10 relative z-10">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-4 tracking-tight">Ready to scan your first post?</h2>
          <p className="text-slate-400 text-sm mb-8 leading-relaxed">Paste, scan, publish safely. Takes less than 10 seconds.</p>
          <button
            onClick={onLaunch}
            className="inline-flex items-center gap-3 px-9 py-4 rounded-full font-bold text-sm text-white transition-all btn-primary shadow-xl shadow-indigo-950/50 hover:scale-105"
          >
            <Rocket className="w-4 h-4" />
            Try It Free Now
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8 px-6 relative z-10 bg-[#090d16]">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-extrabold text-sm text-slate-300">OSINTGuard</span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Built for digital privacy. Zero logs retained.</p>
        </div>
      </footer>
    </div>
  );
}
