import { useState, useRef } from 'react';
import {
  Shield, ArrowLeft, Search, Copy, Check, AlertTriangle,
  CheckCircle, Loader2, Zap, Terminal, Info, ChevronDown, X, Sparkles, Sliders
} from 'lucide-react';

const SeverityBadge = ({ severity }) => {
  const map = {
    High: 'text-rose-300 border-rose-500/40 bg-rose-500/15 shadow-[0_0_12px_rgba(244,63,94,0.2)]',
    Medium: 'text-amber-300 border-amber-500/40 bg-amber-500/15 shadow-[0_0_12px_rgba(245,158,11,0.2)]',
    Low: 'text-cyan-300 border-cyan-500/40 bg-cyan-500/15 shadow-[0_0_12px_rgba(6,182,212,0.2)]',
  };
  const dot = {
    High: 'bg-rose-400 animate-pulse',
    Medium: 'bg-amber-400',
    Low: 'bg-cyan-400',
  };
  const cls = map[severity] || map.Low;
  const d = dot[severity] || dot.Low;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full border text-xs font-semibold font-mono tracking-wide ${cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${d}`} />
      {severity}
    </span>
  );
};

const RiskCard = ({ risk }) => (
  <div className="glass-card rounded-2xl p-4 transition-all duration-300 border border-white/10 hover:border-cyan-500/40 hover:shadow-[0_4px_20px_rgba(56,189,248,0.1)]">
    <div className="flex items-start justify-between gap-3 mb-2">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center flex-shrink-0">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
        </div>
        <span className="text-white font-bold text-sm tracking-tight">{risk.detected_risk}</span>
      </div>
      <SeverityBadge severity={risk.severity} />
    </div>
    <p className="text-slate-400 text-xs leading-relaxed ml-9 font-normal">{risk.hacker_tactic}</p>
  </div>
);

const EXAMPLE_TEXTS = [
  "Hey LinkedIn! Excited to share that I just wrapped up our Q3 product review for Project Helios at TechCorp. We're running it on AWS us-east-2 with our internal tool Nexus v2.3. Heading to the NYC office on Thursday for the big launch meeting!",
  "Just fixed a nasty bug in prod at work. Our main API runs on Python 3.9 on an Ubuntu 22.04 server. The issue was in the /api/v2/users endpoint. Working remotely from San Francisco today ☕",
  "My name is John. My Windows 11 22H2 laptop is acting weird when I connect to my office VPN at 192.168.1.0/24. Anyone else using Cisco AnyConnect 4.10 having issues?"
];

const CONTENT_TYPES = [
  'General',
  'Technical',
  'Professional',
  'Personal',
  'Project / Development'
];

export default function ScannerDashboard({ onBack }) {
  const [inputText, setInputText] = useState('');
  const [contentType, setContentType] = useState('General');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const textareaRef = useRef(null);

  const handleTextChange = (e) => {
    setInputText(e.target.value);
    setCharCount(e.target.value.length);
    if (error) setError(null);
  };

  const loadExample = (text) => {
    setInputText(text);
    setCharCount(text.length);
    setResult(null);
    setError(null);
    textareaRef.current?.focus();
  };

  const handleAnalyze = async () => {
    if (!inputText.trim()) return;
    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      // Use VITE_API_URL if defined, otherwise use relative URL to leverage Vite's proxy config
      const apiBaseUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${apiBaseUrl}/api/analyze-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText, content_type: contentType }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to connect to the analysis server. Make sure Python Flask server is running (python app.py).');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.rewritten_text) return;
    await navigator.clipboard.writeText(result.rewritten_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const highCount = result?.warnings?.filter(w => w.severity === 'High').length ?? 0;
  const medCount = result?.warnings?.filter(w => w.severity === 'Medium').length ?? 0;

  return (
    <div className="min-h-screen bg-[#090d16] bg-grid-pattern flex flex-col relative overflow-x-hidden text-slate-100 font-sans">

      {/* Ambient background glows */}
      <div className="absolute top-0 right-1/4 w-[600px] h-[300px] bg-indigo-900/15 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-[600px] h-[300px] bg-cyan-900/15 blur-[140px] pointer-events-none" />

      {/* ── Top Bar (Nexus AI Floating Header) ── */}
      <header className="sticky top-0 z-40 border-b border-white/10 backdrop-blur-xl bg-[#090d16]/85 px-4 sm:px-8 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="flex items-center gap-2 text-slate-400 hover:text-white text-xs font-semibold px-3 py-1.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 transition-all group"
            >
              <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
              <span>Back</span>
            </button>
            <div className="w-px h-5 bg-white/10" />
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center shadow-[0_0_12px_rgba(56,189,248,0.4)]">
                <Shield className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="font-extrabold text-sm text-white tracking-tight">
                OSINT<span className="text-cyan-400">Guard</span>
              </span>
              <span className="text-xs font-mono text-cyan-300/60 hidden sm:inline">/ AI Scanner</span>
            </div>
          </div>

          {/* Pill Tabs & Status Chips */}
          <div className="flex items-center gap-3">
            {result && (
              <div className="flex items-center gap-2">
                {highCount > 0 && (
                  <span className="text-xs font-mono px-3 py-1 rounded-full text-rose-300 border border-rose-500/40 bg-rose-500/15 font-semibold">
                    {highCount} HIGH
                  </span>
                )}
                {medCount > 0 && (
                  <span className="text-xs font-mono px-3 py-1 rounded-full text-amber-300 border border-amber-500/40 bg-amber-500/15 font-semibold">
                    {medCount} MED
                  </span>
                )}
              </div>
            )}
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
              <span className="text-[11px] font-mono text-emerald-300 font-bold">ONLINE</span>
            </div>
          </div>

        </div>
      </header>

      {/* ── Main Dashboard Content ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">

          {/* ── LEFT PANEL (Input Draft Widget) ── */}
          <div className="glass-card rounded-3xl p-6 sm:p-7 border border-white/10 flex flex-col gap-5 shadow-2xl relative">
            
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center">
                  <Terminal className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-white tracking-tight">INPUT DRAFT</h2>
                  <p className="text-[11px] text-slate-400 font-normal">Paste social post or AI prompt</p>
                </div>
              </div>

              {/* Load Example Dropdown */}
              <div className="relative group">
                <button className="flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white transition-all border border-white/10 rounded-full px-3.5 py-1.5 bg-slate-900/80 hover:bg-slate-800 shadow-sm">
                  <Zap className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Load Sample</span>
                  <ChevronDown className="w-3.5 h-3.5 opacity-70" />
                </button>
                <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl p-2 shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-30 bg-[#0d1322] border border-white/15 backdrop-blur-xl">
                  <p className="text-[10px] font-mono text-cyan-300 px-3 py-1 uppercase tracking-widest font-semibold">Select Test Scenario</p>
                  {EXAMPLE_TEXTS.map((t, i) => (
                    <button
                      key={i}
                      onClick={() => loadExample(t)}
                      className="w-full text-left text-xs text-slate-300 hover:text-white rounded-xl p-3 transition-colors line-clamp-2 hover:bg-white/10 font-normal"
                    >
                      {t.slice(0, 95)}…
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Textarea Box */}
            <div className="relative flex-1">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={handleTextChange}
                placeholder={"Paste your social media draft here...\n\ne.g. \"Excited to share that I just wrapped up Q3 planning at TechCorp. Meeting the team in NYC next Monday!\""}
                className="w-full h-64 lg:h-72 rounded-2xl p-5 text-slate-100 placeholder-slate-500 text-sm leading-relaxed resize-none focus:outline-none transition-all scrollbar-thin bg-slate-950/70 border border-white/10 focus:border-cyan-400/50 focus:shadow-[0_0_20px_rgba(56,189,248,0.15)] font-sans"
              />
              <div className="absolute bottom-4 right-4 text-[11px] font-mono text-slate-500 px-2.5 py-1 rounded-full bg-slate-900/80 border border-white/5">
                {charCount} chars
              </div>
            </div>

            {/* Content Type Selector */}
            <div className="flex flex-col gap-2.5 p-4 rounded-2xl border border-white/10 bg-slate-950/50 backdrop-blur-md shadow-inner">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">Content Type</span>
                </div>
                <span className="text-[11px] font-mono text-cyan-300 font-semibold px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                  {contentType}
                </span>
              </div>
              <div className="flex flex-wrap gap-2 mt-0.5">
                {CONTENT_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setContentType(type)}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
                      contentType === type
                        ? 'bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 text-white shadow-[0_0_15px_rgba(56,189,248,0.35)] border border-cyan-400/50 scale-[1.02]'
                        : 'bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200 border border-white/10'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-start gap-3 rounded-2xl px-4 py-3 border border-rose-500/40 bg-rose-500/15 shadow-[0_0_15px_rgba(244,63,94,0.15)]">
                <X className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-rose-300 text-xs font-bold">Analysis Failed</p>
                  <p className="text-rose-400/90 text-xs mt-0.5 font-normal">{error}</p>
                </div>
              </div>
            )}

            {/* Action Button */}
            <button
              onClick={handleAnalyze}
              disabled={isLoading || !inputText.trim()}
              className={`flex items-center justify-center gap-2.5 w-full py-4 rounded-full font-bold text-sm transition-all duration-300 ${
                isLoading || !inputText.trim()
                  ? 'bg-slate-900/80 text-slate-500 cursor-not-allowed border border-white/5'
                  : 'btn-primary text-white shadow-xl shadow-indigo-950/60 hover:scale-[1.01]'
              }`}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Scanning Threat Vectors…</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Analyze for OSINT Leaks</span>
                </>
              )}
            </button>

            {/* Footer info tip */}
            <div className="flex items-start gap-3 rounded-2xl px-4 py-3 border border-white/5 bg-white/5">
              <Info className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
              <p className="text-slate-400 text-xs leading-relaxed font-normal">
                Detects PII, exact location traces, system/device details, corporate identifiers, and habit patterns used in spear-phishing attacks.
              </p>
            </div>

          </div>

          {/* ── RIGHT PANEL (Analysis Output Widget) ── */}
          <div className="glass-card rounded-3xl p-6 sm:p-7 border border-white/10 flex flex-col gap-5 shadow-2xl relative">

            {/* Empty State */}
            {!result && !isLoading && (
              <div className="flex-1 flex flex-col items-center justify-center text-center min-h-80 border border-dashed border-white/10 rounded-2xl p-8 bg-slate-950/40">
                <div className="relative mb-4">
                  <div className="w-16 h-16 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shadow-lg">
                    <Shield className="w-8 h-8 text-indigo-400/60" />
                  </div>
                </div>
                <h3 className="text-white font-bold text-base mb-1">Awaiting Draft Input</h3>
                <p className="text-slate-400 text-xs max-w-xs leading-relaxed">Paste your text on the left and click Analyze. Results, sanitized rewrite, and risk severity breakdown will render here.</p>
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="flex-1 flex flex-col items-center justify-center min-h-80 rounded-2xl border border-white/10 bg-slate-950/50">
                <div className="relative mb-5">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-indigo-600/20 to-cyan-500/20 border border-cyan-400/30 flex items-center justify-center animate-pulse">
                    <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
                  </div>
                </div>
                <p className="text-white font-mono text-xs font-bold tracking-wider">RUNNING DEEP OSINT ANALYSIS…</p>
                <p className="text-slate-400 text-xs mt-1 font-medium">Cross-referencing 47 threat vectors</p>
              </div>
            )}

            {/* Analysis Results */}
            {result && (
              <>
                {/* Clean Safe Rewrite */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                    <h2 className="text-xs font-bold text-white font-mono tracking-wider uppercase">SAFE TO PUBLISH VERSION</h2>
                  </div>
                  <div className="relative rounded-2xl p-5 border border-white/15 bg-slate-950/80 shadow-inner">
                    <p className="text-slate-100 text-sm leading-relaxed pr-12 font-normal">
                      {result.rewritten_text}
                    </p>
                    <button
                      onClick={handleCopy}
                      className="absolute top-4 right-4 w-9 h-9 rounded-full flex items-center justify-center transition-all border border-white/15 bg-white/10 hover:bg-cyan-500/20 hover:border-cyan-400/40 text-slate-200 hover:text-white"
                      title="Copy to clipboard"
                    >
                      {copied
                        ? <Check className="w-4 h-4 text-emerald-400" />
                        : <Copy className="w-4 h-4" />
                      }
                    </button>
                    {copied && (
                      <span className="absolute top-5 right-15 text-xs text-emerald-400 font-mono font-bold">Copied!</span>
                    )}
                  </div>
                </div>

                {/* Risks Breakdown */}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      </div>
                      <h2 className="text-xs font-bold text-white font-mono tracking-wider uppercase">DETECTED OSINT RISKS</h2>
                    </div>
                    <span className="text-xs font-mono font-semibold text-cyan-300 border border-white/10 px-3 py-0.5 rounded-full bg-white/5">
                      {result.warnings?.length ?? 0} found
                    </span>
                  </div>

                  {result.warnings?.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 border border-dashed border-white/10 rounded-2xl bg-slate-950/40">
                      <CheckCircle className="w-8 h-8 text-emerald-400 mb-2" />
                      <p className="text-white font-bold text-sm">No risks detected!</p>
                      <p className="text-slate-400 text-xs mt-0.5">Your draft appears completely safe to publish.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 max-h-[380px] overflow-y-auto scrollbar-thin pr-1">
                      {result.warnings.map((w, i) => (
                        <RiskCard key={i} risk={w} />
                      ))}
                    </div>
                  )}
                </div>

                {/* Scan another post button */}
                <button
                  onClick={() => { setResult(null); setInputText(''); setCharCount(0); }}
                  className="flex items-center justify-center gap-2 w-full py-3 rounded-full text-xs font-semibold text-slate-300 hover:text-white transition-all border border-white/10 bg-white/5 hover:bg-white/10 mt-2"
                >
                  <Search className="w-3.5 h-3.5" />
                  Scan another post draft
                </button>
              </>
            )}

          </div>

        </div>
      </main>
    </div>
  );
}
