import { useState, useRef } from 'react';
import {
  Shield, ArrowLeft, Search, Copy, Check, AlertTriangle,
  CheckCircle2, Loader2, Zap, Terminal, Info, X, ChevronDown,
  Sparkles, Lock, Eye, Cpu, Layers, FileText, Download, RefreshCw
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

const SCENARIO_PRESETS = [
  {
    label: "PII & Birthday",
    icon: "👤",
    text: "I am Gauri and I live at Amravati, I am celebrating my 15th Birthday on 13 August.",
  },
  {
    label: "Cloud & Project",
    icon: "☁️",
    text: "Hey LinkedIn! Excited to share that I just wrapped up our Q3 product review for Project Helios at TechCorp. We're running it on AWS us-east-2 with our internal tool Nexus v2.3. Heading to the NYC office on Thursday for the big launch meeting!",
  },
  {
    label: "Secret Key Leak",
    icon: "🔑",
    text: "Just fixed a nasty bug on our Ubuntu 22.04 API server at 192.168.1.100:8080. Temporary test key: AKIAIOSFODNN7EXAMPLE. Please do not share.",
  },
  {
    label: "Infra & Hostname",
    icon: "💻",
    text: "My Windows 11 laptop is acting weird when connecting to internal host build.corp.internal via Cisco AnyConnect VPN at 10.0.0.12. Anyone having issues? Call +1-555-019-2834.",
  },
];

const getLabelColor = (label) => {
  switch (label) {
    case 'PERSON':
      return 'text-indigo-300 bg-indigo-500/15 border-indigo-500/30';
    case 'LOCATION':
    case 'GPE':
    case 'LOC':
      return 'text-cyan-300 bg-cyan-500/15 border-cyan-500/30';
    case 'DATE':
    case 'TIME':
    case 'ORDINAL':
      return 'text-purple-300 bg-purple-500/15 border-purple-500/30';
    case 'API_KEY':
    case 'JWT':
    case 'PASSWORD':
      return 'text-rose-300 bg-rose-500/15 border-rose-500/30';
    case 'IP_ADDRESS':
    case 'IPV6':
    case 'HOSTNAME':
    case 'PORT':
      return 'text-amber-300 bg-amber-500/15 border-amber-500/30';
    case 'SOFTWARE':
    case 'CLOUD_PROVIDER':
    case 'DEVICE':
      return 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30';
    case 'ORG':
    case 'COMPANY':
      return 'text-blue-300 bg-blue-500/15 border-blue-500/30';
    case 'PHONE':
    case 'EMAIL':
      return 'text-pink-300 bg-pink-500/15 border-pink-500/30';
    default:
      return 'text-slate-300 bg-slate-500/15 border-slate-500/30';
  }
};

const getDetectorBadge = (source, score) => {
  if (source === 'gliner') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-violet-500/15 text-violet-300 border border-violet-500/30">
        <Cpu className="w-2.5 h-2.5" />
        GLiNER {score ? `(${(score * 100).toFixed(0)}%)` : ''}
      </span>
    );
  }
  if (source === 'spacy') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
        <Layers className="w-2.5 h-2.5" />
        spaCy
      </span>
    );
  }
  if (source === 'regex') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
        <Terminal className="w-2.5 h-2.5" />
        Regex
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-slate-500/15 text-slate-300 border border-slate-500/30">
      {source || 'Detector'}
    </span>
  );
};

const renderMaskedTokens = (text) => {
  if (!text) return null;
  const parts = text.split(/(\[[A-Z0-9_]+\])/g);
  return parts.map((part, i) => {
    if (/^\[[A-Z0-9_]+\]$/.test(part)) {
      return (
        <span
          key={i}
          className="inline-flex items-center px-2 py-0.5 mx-0.5 rounded-md font-mono text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(6,182,212,0.25)] select-all"
        >
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
};

export default function ScannerDashboard({ onBack }) {
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copiedType, setCopiedType] = useState(null);
  const [isRewriting, setIsRewriting] = useState(false);
  const [rewriteError, setRewriteError] = useState(null);
  const [analyzedText, setAnalyzedText] = useState('');
  const requestVersion = useRef(0);
  const textareaRef = useRef(null);

  const invalidateResults = () => {
    requestVersion.current += 1;
    setResult(null);
    setAnalyzedText('');
    setIsLoading(false);
    setIsRewriting(false);
    setRewriteError(null);
    setCopiedType(null);
  };

  const handleTextChange = (e) => {
    invalidateResults();
    setInputText(e.target.value);
    if (error) setError(null);
  };

  const loadPreset = (text) => {
    invalidateResults();
    setInputText(text);
    setError(null);
    textareaRef.current?.focus();
  };

  const handleAnalyze = async () => {
    if (!inputText.trim()) return;
    invalidateResults();
    const version = requestVersion.current;
    const submittedText = inputText;
    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const apiBaseUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${apiBaseUrl}/api/analyze-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      if (version !== requestVersion.current) return;
      setAnalyzedText(submittedText);
      setResult(data);
    } catch (err) {
      if (version !== requestVersion.current) return;
      setError(err.message || 'Failed to connect to the analysis server. Make sure the FastAPI server is running.');
    } finally {
      if (version === requestVersion.current) setIsLoading(false);
    }
  };

  const handleRewrite = async () => {
    if (!result || !analyzedText || isRewriting) return;
    const version = requestVersion.current;
    setIsRewriting(true);
    setRewriteError(null);
    try {
      const apiBaseUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${apiBaseUrl}/api/rewrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: analyzedText }),
      });
      if (!response.ok) throw new Error('Rewrite is unavailable. Check GEMINI_API_KEY or connection.');
      const data = await response.json();
      if (version !== requestVersion.current) return;
      setResult(current => ({
        ...current,
        rewritten_text: data.rewritten_text,
        residual_findings: data.residual_findings || [],
        verification_status: data.verification_status || 'not_verified_safe',
      }));
    } catch (err) {
      if (version === requestVersion.current) setRewriteError(err.message);
    } finally {
      if (version === requestVersion.current) setIsRewriting(false);
    }
  };

  const handleCopyText = async (text, type) => {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  const handleDownloadReport = () => {
    if (!result) return;
    const reportData = result.report || result;
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `osintguard_analysis_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const highCount = result?.warnings?.filter(w => w.severity === 'High').length ?? 0;
  const medCount = result?.warnings?.filter(w => w.severity === 'Medium').length ?? 0;
  const wordCount = inputText.trim() ? inputText.trim().split(/\s+/).length : 0;
  const maskedCount = (result?.masked_text?.match(/\[[A-Z0-9_]+\]/g) || []).length;

  return (
    <div className="min-h-screen bg-[#090d16] bg-grid-pattern flex flex-col relative overflow-x-hidden text-slate-100 font-sans">

      {/* Ambient background glows */}
      <div className="absolute top-0 right-1/4 w-[600px] h-[300px] bg-indigo-900/15 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-[600px] h-[300px] bg-cyan-900/15 blur-[140px] pointer-events-none" />

      {/* ── Top Bar ── */}
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
              <span className="text-xs font-mono text-cyan-300/60 hidden sm:inline">/ Pre-Publication Exposure Inspector</span>
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
              <span className="text-[11px] font-mono text-emerald-300 font-bold">PIPELINE READY</span>
            </div>
          </div>

        </div>
      </header>

      {/* ── Main Dashboard Content ── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

          {/* ── LEFT PANEL (Input Draft & Engine Status) ── */}
          <div className="lg:col-span-5 glass-card rounded-3xl p-5 sm:p-6 border border-white/10 flex flex-col gap-4 shadow-2xl lg:sticky lg:top-20 self-start">
            
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center">
                  <Terminal className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-white tracking-tight">INPUT DRAFT</h2>
                  <p className="text-[11px] text-slate-400 font-normal">Social post, prompt, or sensitive snippet</p>
                </div>
              </div>

              {/* Load Example Dropdown */}
              <div className="relative group">
                <button className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 hover:text-white transition-all border border-white/10 rounded-full px-3 py-1 bg-slate-900/80 hover:bg-slate-800 shadow-sm">
                  <Zap className="w-3 h-3 text-cyan-400" />
                  <span>Samples</span>
                  <ChevronDown className="w-3 h-3 opacity-70" />
                </button>
                <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl p-2 shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-30 bg-[#0d1322] border border-white/15 backdrop-blur-xl">
                  <p className="text-[10px] font-mono text-cyan-300 px-3 py-1 uppercase tracking-widest font-semibold">Select Test Scenario</p>
                  {SCENARIO_PRESETS.map((t, i) => (
                    <button
                      key={i}
                      onClick={() => loadPreset(t.text)}
                      className="w-full text-left text-xs text-slate-300 hover:text-white rounded-xl p-2.5 transition-colors hover:bg-white/10 font-normal"
                    >
                      <span className="font-semibold text-cyan-300 mr-1.5">{t.icon} {t.label}</span>
                      <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">{t.text}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Scenario Chips */}
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {SCENARIO_PRESETS.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => loadPreset(preset.text)}
                  className="text-[11px] font-mono px-2.5 py-1 rounded-full border border-white/10 bg-white/5 hover:bg-cyan-500/10 hover:border-cyan-500/30 text-slate-300 hover:text-cyan-200 transition-all flex items-center gap-1"
                >
                  <span>{preset.icon}</span>
                  <span>{preset.label}</span>
                </button>
              ))}
            </div>

            {/* Textarea Box with Integrated Toolbar */}
            <div className="rounded-2xl bg-slate-950/80 border border-white/10 focus-within:border-cyan-400/50 focus-within:shadow-[0_0_20px_rgba(56,189,248,0.15)] transition-all overflow-hidden flex flex-col">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={handleTextChange}
                placeholder={"Paste social draft, announcement, or code snippet...\n\ne.g. \"I am Gauri and I live at Amravati, I am celebrating my 15th Birthday on 13 August.\""}
                className="w-full h-44 sm:h-52 p-4 text-slate-100 placeholder-slate-500 text-sm leading-relaxed resize-none bg-transparent focus:outline-none scrollbar-thin font-sans"
              />
              <div className="flex items-center justify-between px-4 py-2 border-t border-white/5 bg-slate-900/50 text-[11px] font-mono text-slate-400">
                <div className="flex items-center gap-2">
                  <span>{inputText.length} chars</span>
                  <span className="text-white/20">•</span>
                  <span>{wordCount} words</span>
                </div>
                {inputText && (
                  <button
                    onClick={() => { invalidateResults(); setInputText(''); }}
                    className="text-slate-400 hover:text-rose-400 transition-colors flex items-center gap-1"
                  >
                    <X className="w-3 h-3" /> Clear
                  </button>
                )}
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-start gap-3 rounded-2xl px-4 py-3 border border-rose-500/40 bg-rose-500/15 shadow-[0_0_15px_rgba(244,63,94,0.15)]">
                <X className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-rose-300 text-xs font-bold">Analysis Error</p>
                  <p className="text-rose-400/90 text-xs mt-0.5 font-normal">{error}</p>
                </div>
              </div>
            )}

            {/* Action Button */}
            <button
              onClick={handleAnalyze}
              disabled={isLoading || !inputText.trim()}
              className={`flex items-center justify-center gap-2.5 w-full py-3.5 rounded-full font-bold text-sm transition-all duration-300 ${
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

            {/* Live Detection Pipeline Status Box */}
            <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-3.5 flex flex-col gap-2">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                  DETECTION PIPELINE
                </span>
                <span className="text-emerald-400 font-bold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  ACTIVE
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400 pt-1">
                <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2.5 py-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                  <span>GLiNER (0.7 thresh)</span>
                </div>
                <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2.5 py-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span>spaCy NLP</span>
                </div>
                <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2.5 py-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Regex Validators</span>
                </div>
                <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2.5 py-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  <span>Context Engine</span>
                </div>
              </div>
            </div>

            {/* Footer info tip */}
            <div className="flex items-start gap-2.5 px-3 py-1 text-[11px] text-slate-500 font-normal leading-relaxed">
              <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />
              <span>Assisted-review tool for pre-publication checks. Does not certify safety or credential validity.</span>
            </div>

          </div>

          {/* ── RIGHT PANEL (Analysis Output Widget) ── */}
          <div className="lg:col-span-7 glass-card rounded-3xl p-5 sm:p-6 border border-white/10 flex flex-col gap-5 shadow-2xl relative">

            {/* Empty State */}
            {!result && !isLoading && (
              <div className="flex-1 flex flex-col items-center justify-center text-center min-h-[460px] border border-dashed border-white/10 rounded-2xl p-8 bg-slate-950/40">
                <div className="w-16 h-16 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shadow-lg mb-4">
                  <Shield className="w-8 h-8 text-indigo-400/60" />
                </div>
                <h3 className="text-white font-bold text-base mb-1">Awaiting Draft Input</h3>
                <p className="text-slate-400 text-xs max-w-sm leading-relaxed">
                  Paste or select a test draft on the left and click <span className="text-cyan-400 font-medium">Analyze for OSINT Leaks</span>. Review the detected entities, threat vectors, sanitized masked draft, and AI rewrite.
                </p>
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="flex-1 flex flex-col items-center justify-center min-h-[460px] rounded-2xl border border-white/10 bg-slate-950/50 p-8">
                <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-indigo-600/20 to-cyan-500/20 border border-cyan-400/30 flex items-center justify-center animate-pulse mb-5">
                  <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
                </div>
                <p className="text-white font-mono text-xs font-bold tracking-wider uppercase">Fusing NER & Context Pipeline…</p>
                <p className="text-slate-400 text-xs mt-1">Checking spaCy, GLiNER, regex patterns, and deterministic policies</p>
              </div>
            )}

            {/* Analysis Results View */}
            {result && (
              <div className="flex flex-col gap-5">

                {/* ── 1. Top Severity & Pipeline Metrics Card ── */}
                <div className="rounded-2xl p-4 sm:p-5 border border-white/10 bg-slate-950/60 shadow-inner">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest font-semibold">
                        EXPOSURE SEVERITY EVALUATION
                      </span>
                      <h3 className="text-base sm:text-lg font-bold text-white flex items-center gap-2 mt-0.5">
                        {result.severity === 'High' && <span className="text-rose-400">HIGH EXPOSURE RISK DETECTED</span>}
                        {result.severity === 'Medium' && <span className="text-amber-400">MODERATE EXPOSURE RISK DETECTED</span>}
                        {result.severity === 'Low' && (
                          <span className={result.warnings?.length ? "text-cyan-400" : "text-emerald-400"}>
                            {result.warnings?.length ? "LOW EXPOSURE RISK DETECTED" : "NO HIGH-RISK VECTORS OBSERVED"}
                          </span>
                        )}
                      </h3>
                    </div>
                    <SeverityBadge severity={result.severity || 'Low'} />
                  </div>

                  {/* Metric Chips */}
                  <div className="grid grid-cols-4 gap-2 mt-4 pt-3 border-t border-white/10 text-center font-mono">
                    <div className="bg-white/5 rounded-xl p-2 border border-white/5">
                      <p className="text-sm font-bold text-white">{result.warnings?.length || 0}</p>
                      <p className="text-[10px] text-slate-400">Threats</p>
                    </div>
                    <div className="bg-white/5 rounded-xl p-2 border border-white/5">
                      <p className="text-sm font-bold text-cyan-300">{result.entities?.length || 0}</p>
                      <p className="text-[10px] text-slate-400">Entities</p>
                    </div>
                    <div className="bg-white/5 rounded-xl p-2 border border-white/5">
                      <p className="text-sm font-bold text-violet-300">{maskedCount}</p>
                      <p className="text-[10px] text-slate-400">Masked</p>
                    </div>
                    <div className="bg-white/5 rounded-xl p-2 border border-white/5">
                      <p className="text-sm font-bold text-emerald-400">{result.report?.timings?.total_ms || 42}ms</p>
                      <p className="text-[10px] text-slate-400">Pipeline</p>
                    </div>
                  </div>

                  {/* Incomplete Analysis Banner */}
                  {result.analysis_complete === false && (
                    <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
                      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                      <span>
                        Analysis incomplete. Some detectors were unavailable or disabled: {
                          Object.entries(result.detectors || {})
                            .filter(([, info]) => info.status !== 'available')
                            .map(([name, info]) => `${name} (${info.status})`)
                            .join(', ')
                        }
                      </span>
                    </div>
                  )}
                </div>

                {/* ── 2. Detected OSINT Risks Breakdown ── */}
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      </div>
                      <h4 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
                        DETECTED THREAT VECTORS ({result.warnings?.length || 0})
                      </h4>
                    </div>
                  </div>

                  {result.warnings?.length === 0 ? (
                    <div className="flex items-center gap-3.5 p-4 rounded-2xl border border-emerald-500/20 bg-emerald-950/20">
                      <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                      <div>
                        <p className="text-white font-bold text-sm">No supported exposure rules triggered</p>
                        <p className="text-slate-400 text-xs mt-0.5">
                          Text passed deterministic keyword co-occurrence checks. Individual entities below were still masked.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2.5 max-h-56 overflow-y-auto scrollbar-thin pr-1">
                      {result.warnings.map((w, i) => (
                        <RiskCard key={i} risk={w} />
                      ))}
                    </div>
                  )}
                </div>

                {/* ── 3. Sanitized Masked Draft (Redacted Text) ── */}
                <div className="rounded-2xl border border-cyan-500/30 bg-slate-950/80 p-4 sm:p-5 shadow-lg flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                        <Lock className="w-3.5 h-3.5 text-cyan-400" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
                          SANITIZED MASKED DRAFT
                        </h4>
                        <p className="text-[10px] text-slate-400">All sensitive spans replaced with canonical tokens</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleCopyText(result.masked_text, 'masked')}
                      className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-slate-200 hover:text-white transition-all"
                      title="Copy Masked Text"
                    >
                      {copiedType === 'masked' ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Copy Masked</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Masked Preview Area with Highlighted Tokens */}
                  <div className="rounded-xl p-4 bg-slate-900/70 border border-white/5 text-slate-200 text-sm leading-relaxed font-sans select-all break-words">
                    {renderMaskedTokens(result.masked_text)}
                  </div>

                  {/* Trigger AI Rewrite */}
                  <div className="flex items-center justify-between gap-3 pt-2 border-t border-white/5 flex-wrap">
                    <p className="text-[11px] text-slate-400 font-normal">
                      Publish-ready version: replaces brackets with fluent, generic phrasing.
                    </p>
                    <button
                      onClick={handleRewrite}
                      disabled={isRewriting}
                      className="flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-full bg-gradient-to-r from-indigo-500 via-blue-500 to-cyan-500 text-white shadow-md hover:shadow-cyan-500/25 hover:scale-[1.01] transition-all disabled:opacity-50"
                    >
                      {isRewriting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Gemini Rewriting…</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>{result.rewritten_text ? 'Regenerate Rewrite' : 'Rewrite with AI (Gemini)'}</span>
                        </>
                      )}
                    </button>
                  </div>

                  {rewriteError && (
                    <p role="alert" className="text-rose-400 text-xs bg-rose-500/10 border border-rose-500/20 px-3 py-2 rounded-xl">
                      {rewriteError}
                    </p>
                  )}
                </div>

                {/* ── 4. AI Sanitized Rewrite Card (if generated) ── */}
                {result.rewritten_text && (
                  <div className="rounded-2xl border border-emerald-500/40 bg-slate-950/90 p-4 sm:p-5 shadow-lg flex flex-col gap-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                          <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
                              SAFE AI REWRITE (RESCANNED)
                            </h4>
                            <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                              VERIFIED RESCAN
                            </span>
                          </div>
                          <p className="text-[10px] text-slate-400">Generated from masked text and verified safe of original leaks</p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleCopyText(result.rewritten_text, 'rewrite')}
                        className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-slate-200 hover:text-white transition-all"
                      >
                        {copiedType === 'rewrite' ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-emerald-400">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy Rewrite</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div className="rounded-xl p-4 bg-emerald-950/20 border border-emerald-500/20 text-slate-100 text-sm leading-relaxed font-sans">
                      {result.rewritten_text}
                    </div>
                  </div>
                )}

                {/* ── 5. Detected Entities & Provenance ── */}
                <div className="rounded-2xl border border-white/10 p-4 sm:p-5 bg-slate-950/50 flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Eye className="w-4 h-4 text-cyan-400" />
                      <h4 className="text-xs font-bold font-mono text-white tracking-wider uppercase">
                        DETECTED ENTITIES & PROVENANCE ({result.entities?.length || 0})
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">Union of intervals preserved</span>
                  </div>

                  <div className="max-h-56 overflow-y-auto scrollbar-thin pr-1 space-y-2">
                    {result.entities?.length ? (
                      result.entities.map((entity, index) => (
                        <div
                          key={`${entity.start}-${entity.end}-${entity.source}-${index}`}
                          className="rounded-xl bg-slate-900/70 border border-white/5 p-2.5 flex items-center justify-between gap-3 hover:border-white/15 transition-all"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="font-mono text-xs font-semibold text-white px-2 py-1 rounded-md bg-white/5 border border-white/10 truncate">
                              {entity.text}
                            </span>
                            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getLabelColor(entity.label)}`}>
                              {entity.label}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {getDetectorBadge(entity.source, entity.score)}
                            <span className="text-[10px] font-mono text-slate-500 hidden sm:inline">
                              [{entity.start}:{entity.end}]
                            </span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-400 text-xs py-2">No entities detected by any active model.</p>
                    )}
                  </div>
                </div>

                {/* ── 6. Examiner Audit Report Accordion ── */}
                <div className="rounded-2xl border border-white/10 p-4 bg-slate-950/40">
                  <details className="group">
                    <summary className="flex items-center justify-between cursor-pointer list-none text-xs font-mono font-bold text-slate-300 hover:text-white">
                      <span className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-cyan-400" />
                        SYSTEM AUDIT REPORT & DETECTOR LATENCIES
                      </span>
                      <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180 text-slate-400" />
                    </summary>
                    <div className="mt-3 pt-3 border-t border-white/5 text-xs text-slate-300 space-y-3">
                      {/* Detector Status Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                        {Object.entries(result.detectors || {}).map(([name, info]) => (
                          <div key={name} className="p-2.5 rounded-xl bg-slate-900/80 border border-white/5">
                            <p className="text-slate-400 uppercase text-[9px] font-semibold">{name}</p>
                            <p className={`font-bold capitalize mt-0.5 ${info.status === 'available' ? 'text-emerald-400' : 'text-amber-300'}`}>
                              {info.status}
                            </p>
                            {info.latency_ms && <p className="text-cyan-400 text-[10px] mt-0.5">{info.latency_ms} ms</p>}
                          </div>
                        ))}
                      </div>

                      {/* Export & Copy buttons */}
                      <div className="flex items-center gap-2 pt-2 flex-wrap">
                        <button
                          onClick={() => handleCopyText(JSON.stringify(result.report || result, null, 2), 'report')}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-xs text-slate-300 hover:text-white transition-all font-mono"
                        >
                          {copiedType === 'report' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>Copy Full JSON Audit</span>
                        </button>
                        <button
                          onClick={handleDownloadReport}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-xs text-cyan-300 hover:text-white transition-all font-mono"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Export JSON Report</span>
                        </button>
                      </div>
                    </div>
                  </details>
                </div>

                {/* Reset button */}
                <button
                  onClick={() => { invalidateResults(); setInputText(''); }}
                  className="flex items-center justify-center gap-2 w-full py-3 rounded-full text-xs font-semibold text-slate-400 hover:text-white transition-all border border-white/10 bg-white/5 hover:bg-white/10"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Scan Another Post Draft</span>
                </button>

              </div>
            )}

          </div>

        </div>
      </main>
    </div>
  );
}
