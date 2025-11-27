import React, { useState, useEffect, useMemo } from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// KARARATLAS UI - Legal Intelligence Platform
// Warm modern fonts, larger cards, smooth tech marquee
// ═══════════════════════════════════════════════════════════════════════════════

const KararatlasApp = () => {
  const [currentPage, setCurrentPage] = useState('landing');
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoaded(true), 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0a0a0a',
      fontFamily: "'Plus Jakarta Sans', -apple-system, sans-serif",
      color: '#fafafa',
      overflow: 'hidden'
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Fraunces:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        ::selection {
          background: rgba(200, 220, 255, 0.2);
          color: #fff;
        }
        
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-12px); }
        }
        
        @keyframes pulse-subtle {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.8; }
        }
        
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
        
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        
        @keyframes gradientFlow {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        
        .nav-link {
          position: relative;
          color: rgba(255, 255, 255, 0.5);
          text-decoration: none;
          font-size: 14px;
          font-weight: 500;
          letter-spacing: 0.2px;
          transition: color 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          cursor: pointer;
          padding: 8px 0;
        }
        
        .nav-link:hover {
          color: rgba(255, 255, 255, 0.95);
        }
        
        .btn-primary {
          background: #fafafa;
          color: #0a0a0a;
          border: none;
          padding: 14px 28px;
          font-size: 14px;
          font-weight: 600;
          font-family: 'Plus Jakarta Sans', sans-serif;
          letter-spacing: 0.2px;
          cursor: pointer;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          border-radius: 6px;
        }
        
        .btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 20px 40px rgba(255, 255, 255, 0.15);
        }
        
        .btn-secondary {
          background: transparent;
          color: rgba(255, 255, 255, 0.8);
          border: 1px solid rgba(255, 255, 255, 0.2);
          padding: 14px 28px;
          font-size: 14px;
          font-weight: 500;
          font-family: 'Plus Jakarta Sans', sans-serif;
          cursor: pointer;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          border-radius: 6px;
        }
        
        .btn-secondary:hover {
          border-color: rgba(255, 255, 255, 0.5);
          background: rgba(255, 255, 255, 0.05);
        }
        
        .input-field {
          width: 100%;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.1);
          padding: 18px 20px;
          color: #fafafa;
          font-size: 15px;
          font-family: 'Plus Jakarta Sans', sans-serif;
          transition: all 0.3s ease;
          outline: none;
          border-radius: 8px;
        }
        
        .input-field::placeholder {
          color: rgba(255, 255, 255, 0.3);
        }
        
        .input-field:focus {
          border-color: rgba(180, 200, 255, 0.4);
          background: rgba(255, 255, 255, 0.06);
        }
        
        .card-glass {
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .card-glass:hover {
          border-color: rgba(255, 255, 255, 0.15);
          transform: translateY(-4px);
          box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
        }

        .section-shift:nth-of-type(odd) {
          background: #0a0a0a;
        }

        .section-shift:nth-of-type(even) {
          background: #0f0f0f;
        }
        
        .marquee-track {
          display: flex;
          animation: marquee 40s linear infinite;
        }
        
        .marquee-track:hover {
          animation-duration: 70s;
        }

        .marquee-card {
          position: relative;
          overflow: hidden;
        }

        .marquee-card::before {
          content: '';
          position: absolute;
          inset: -120%;
          background: conic-gradient(from 180deg, rgba(147, 197, 253, 0.3), rgba(140, 120, 200, 0.2), transparent 40%);
          animation: spin 8s linear infinite;
          opacity: 0;
          transition: opacity 0.4s ease;
        }

        .marquee-card:hover::before {
          opacity: 1;
        }

        .marquee-card::after {
          content: '';
          position: absolute;
          inset: 1px;
          border-radius: 14px;
          background: rgba(255,255,255,0.02);
          backdrop-filter: blur(2px);
          z-index: 0;
        }

        .marquee-card > * {
          position: relative;
          z-index: 1;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .nav-link::after {
          content: '';
          position: absolute;
          left: 0;
          bottom: 0;
          width: 100%;
          height: 2px;
          background: linear-gradient(90deg, #93c5fd 0%, #c4b5fd 100%);
          transform: scaleX(0);
          transform-origin: left;
          transition: transform 0.3s ease;
          border-radius: 2px;
        }

        .nav-link:hover::after {
          transform: scaleX(1);
        }

        .magnetic-btn {
          position: relative;
          overflow: hidden;
          isolation: isolate;
        }

        .magnetic-btn::after {
          content: '';
          position: absolute;
          inset: -30%;
          background: radial-gradient(circle at center, rgba(255,255,255,0.35), transparent 55%);
          opacity: 0;
          transition: opacity 0.3s ease, transform 0.3s ease;
          z-index: 0;
        }

        .magnetic-btn:hover::after {
          opacity: 1;
          transform: scale(1.05);
        }

        .btn-primary, .btn-secondary {
          position: relative;
          z-index: 1;
          overflow: hidden;
        }

        .ripple-btn::after {
          content: '';
          position: absolute;
          inset: -40%;
          background: radial-gradient(circle at center, rgba(0,0,0,0.08), transparent 55%);
          transform: scale(0);
          transition: transform 0.45s ease, opacity 0.45s ease;
          opacity: 0;
          z-index: 0;
        }

        .ripple-btn:hover::after {
          transform: scale(1.1);
          opacity: 1;
        }

        .noise-overlay {
          position: fixed;
          inset: 0;
          pointer-events: none;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'%3E%3Cfilter id='n' x='0' y='0'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
          mix-blend-mode: soft-light;
        }

        .floating-orb {
          position: absolute;
          filter: blur(60px);
          opacity: 0.55;
        }

        .source-chip:hover {
          transform: translateY(-2px) scale(1.02);
          box-shadow: 0 12px 30px rgba(0,0,0,0.08);
        }

        .stat-count {
          display: inline-block;
          min-width: 64px;
        }

        .hero-demo {
          position: relative;
          overflow: hidden;
          background: linear-gradient(150deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
          border-radius: 18px;
          border: 1px solid rgba(255,255,255,0.08);
          box-shadow: 0 30px 80px rgba(0,0,0,0.18);
        }

        .hero-demo::before {
          content: '';
          position: absolute;
          inset: -1px;
          border-radius: 18px;
          background: linear-gradient(120deg, rgba(147,197,253,0.25), rgba(140,120,200,0.18), transparent 60%);
          opacity: 0.7;
          z-index: 0;
        }

        .hero-demo::after {
          content: '';
          position: absolute;
          inset: 0;
          background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
          background-size: 28px 28px;
          mix-blend-mode: soft-light;
          opacity: 0.6;
          z-index: 0;
        }

        .light-beam {
          position: absolute;
          top: -10%;
          right: -20%;
          width: 320px;
          height: 320px;
          background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18), transparent 60%);
          transform: rotate(18deg);
          filter: blur(20px);
          opacity: 0.7;
        }
        
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 3px; }
      `}</style>
      <div className="noise-overlay" />
      
      {currentPage === 'landing' && <LandingPage onNavigate={setCurrentPage} isLoaded={isLoaded} />}
      {currentPage === 'register' && <RegisterPage onNavigate={setCurrentPage} />}
      {currentPage === 'features' && <FeaturesPage onNavigate={setCurrentPage} />}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE 1: LANDING / HERO
// ═══════════════════════════════════════════════════════════════════════════════

const LandingPage = ({ onNavigate, isLoaded }) => {
  const [typingText, setTypingText] = useState('');
  const [showAnswer, setShowAnswer] = useState(false);
  const [activeDemo, setActiveDemo] = useState(0);
  const [parallaxY, setParallaxY] = useState(0);
  const [statValues, setStatValues] = useState([0, 0, 0]);
  const [hoveredRef, setHoveredRef] = useState(null);
  const [copied, setCopied] = useState(false);
  const [persona, setPersona] = useState('avukat');
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);
  const [progressStep, setProgressStep] = useState(0);

  const demoVariants = [
    {
      persona: 'avukat',
      question: "Kat karşılığı inşaat sözleşmesinde yüklenicinin temerrüdü halinde arsa sahibinin sözleşmeden dönme hakkını kullanabilmesi için ifa için ek süre vermesi zorunlu mudur? İstisnaları nelerdir?",
      summary: "Yargıtay 15. ve 23. HD yerleşik içtihat: kural olarak ek süre verilmeli (TBK 123). İstisnalar: anlamsız gecikme, kesin vade, borçlunun imkansızlık beyanı.",
      refs: [
        { hd: '15. HD', no: '2021/4892', info: 'Süre verilmeden fesih şartları' },
        { hd: '23. HD', no: '2022/1156', info: 'Kesin vadeli işlemlerde temerrüt' },
        { hd: '15. HD', no: '2020/3847', info: 'İfa imkansızlığı beyanı' }
      ],
      rules: [
        { title: 'TBK 123 - Süre Verme Zorunluluğu', count: 847, color: '#6385b5' },
        { title: 'Ek Süre İstisnaları', count: 234, color: '#8b7cc9' },
        { title: 'Kat Karşılığı İnşaat - Temerrüt', count: 1203, color: '#5a9a8b' }
      ],
      citations: [
        '15. HD 2021/4892 K.',
        '23. HD 2022/1156 K.',
        '15. HD 2023/892 K.',
        '15. HD 2020/3847 K.'
      ]
    },
    {
      persona: 'akademisyen',
      question: "İşyeri kira bedelinin TÜFE oranında artırılmasına itirazda hangi içtihatlar uygulanır? Hakimin müdahalesinin sınırı nedir?",
      summary: "Kira tespitinde TÜFE sınırı ve dürüstlük kuralı birlikte değerlendirilir. 3. HD, sözleşme serbestisi + emsal rayiç dengesi vurgular; tek taraflı fahiş artış reddedilir.",
      refs: [
        { hd: '3. HD', no: '2023/4156', info: 'TÜFE sınırı ve hakkaniyet' },
        { hd: '6. HD', no: '2022/2178', info: 'Rayiç denge' },
        { hd: '3. HD', no: '2021/982', info: 'Fahiş artışın reddi' }
      ],
      rules: [
        { title: 'TBK 344 - TÜFE Sınırı', count: 412, color: '#5a9a8b' },
        { title: 'Rayiç Denge ve Hakkaniyet', count: 301, color: '#6385b5' },
        { title: 'Sözleşme Serbestisi Sınırları', count: 129, color: '#8b7cc9' }
      ],
      citations: [
        '3. HD 2023/4156 K.',
        '6. HD 2022/2178 K.',
        '3. HD 2021/982 K.'
      ]
    },
    {
      persona: 'kurum',
      question: "Haksız rekabet iddiasında internet içerikleri için ihtiyati tedbir şartları nelerdir? Delil saklama nasıl sağlanır?",
      summary: "Haksız rekabet URL'lerinde hızlı delil muhafazası gerekir. 11. HD, içerik kaldırma + erişim engeli için açık ihlal göstergesi ve acil tehlike şartını arar; noter tespiti önerilir.",
      refs: [
        { hd: '11. HD', no: '2022/1456', info: 'Açık ihlal göstergesi' },
        { hd: '11. HD', no: '2023/2789', info: 'Erişim engeli kriterleri' },
        { hd: '7. HD', no: '2021/3341', info: 'Delil muhafazası' }
      ],
      rules: [
        { title: 'Haksız Rekabet Tedbirleri', count: 287, color: '#6385b5' },
        { title: 'Dijital Delil Saklama', count: 156, color: '#8b7cc9' },
        { title: 'Erişim Engeli Kriterleri', count: 198, color: '#5a9a8b' }
      ],
      citations: [
        '11. HD 2023/2789 K.',
        '11. HD 2022/1456 K.',
        '7. HD 2021/3341 K.'
      ]
    }
  ];

  const techItems = [
    { name: 'Vektör Arama', desc: 'Anlam bazlı eşleşme' },
    { name: 'Özel Eğitilmiş AI', desc: 'Türk hukuku için optimize' },
    { name: 'Akıllı Sıralama', desc: 'En alakalı sonuçlar önce' },
    { name: 'Bağlamsal Anlama', desc: 'Sorunuzu tam anlıyor' },
    { name: 'Kaynak Doğrulama', desc: 'Her yanıt atıflı' },
    { name: 'Gerçek Zamanlı', desc: 'Saniyeler içinde sonuç' },
  ];

  const personaLabels = [
    { key: 'avukat', label: 'Avukat' },
    { key: 'akademisyen', label: 'Akademisyen' },
    { key: 'kurum', label: 'Kurum' }
  ];
  const personaColors = {
    avukat: '#6fb1ff',
    akademisyen: '#a88bff',
    kurum: '#5fc2a1'
  };

  const progressSteps = [
    { label: 'İndeks taranıyor', duration: 600 },
    { label: 'Emsal sıralama', duration: 700 },
    { label: 'Özetleniyor', duration: 800 }
  ];

  useEffect(() => {
    const onScroll = () => {
      setParallaxY(window.scrollY * 0.06);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    const targets = [9.5, 0.5, 0.2];
    const start = performance.now();
    const duration = 1200;
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      setStatValues(targets.map(t => +(t * progress).toFixed(2)));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [isLoaded]);

  // Persona filtered active demo
  const personaDemos = useMemo(
    () => demoVariants.filter(d => d.persona === persona),
    [persona]
  );
  const active = personaDemos.length
    ? personaDemos[activeDemo % personaDemos.length]
    : null;

  useEffect(() => {
    if (!personaDemos.length) return;
    if (activeDemo >= personaDemos.length) setActiveDemo(0);
  }, [personaDemos.length, activeDemo]);

  const handleRefClick = (idx) => {
    setActiveDemo(idx);
    simulateLoading();
  };

  const handleCopySummary = () => {
    if (!active) return;
    navigator.clipboard?.writeText(active.summary).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    }).catch(() => {});
  };

  const formatStat = (value, idx) => {
    if (idx === 0) return `${value.toFixed(1)}M`;
    if (idx === 1) return `${Math.round(value * 1000)}K`;
    return `${Math.round(value * 1000)}K`;
  };

  const simulateLoading = () => {
    setIsLoadingDemo(true);
    setProgressStep(0);
    let step = 0;
    const timers = progressSteps.map((s, i) => setTimeout(() => {
      step = i;
      setProgressStep(step);
    }, progressSteps.slice(0, i).reduce((a, b) => a + b.duration, 0)));
    const total = progressSteps.reduce((a, b) => a + b.duration, 0) + 300;
    const done = setTimeout(() => {
      setIsLoadingDemo(false);
      setProgressStep(progressSteps.length - 1);
    }, total);
    return () => {
      timers.forEach(t => clearTimeout(t));
      clearTimeout(done);
    };
  };

  useEffect(() => {
    if (!isLoaded) return;
    if (!personaDemos.length) return;
    const question = personaDemos[activeDemo % personaDemos.length].question;
    let i = 0;
    setTypingText('');
    setShowAnswer(false);
    const stopLoad = simulateLoading();
    const typeInterval = setInterval(() => {
      if (i <= question.length) {
        setTypingText(question.slice(0, i));
        i++;
      } else {
        clearInterval(typeInterval);
        setTimeout(() => setShowAnswer(true), 500);
      }
    }, 18);
    return () => {
      clearInterval(typeInterval);
      stopLoad?.();
    };
  }, [isLoaded, activeDemo, persona, personaDemos]);

  return (
    <div style={{ minHeight: '100vh', position: 'relative' }}>
      {/* Gradient orbs */}
      <div className="floating-orb" style={{
        top: '-20%',
        left: '-10%',
        width: '600px',
        height: '600px',
        background: 'radial-gradient(circle, rgba(99, 133, 181, 0.18) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />
      <div className="floating-orb" style={{
        bottom: '-30%',
        right: '-10%',
        width: '820px',
        height: '820px',
        background: 'radial-gradient(circle, rgba(140, 120, 200, 0.12) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />
      <div className="floating-orb" style={{
        top: '40%',
        right: '60%',
        width: '420px',
        height: '420px',
        background: 'radial-gradient(circle, rgba(90, 154, 139, 0.08) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />
      
      {/* Navigation */}
      <nav style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        padding: '20px 48px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 100,
        background: 'linear-gradient(180deg, rgba(10,10,10,0.9) 0%, transparent 100%)',
        opacity: isLoaded ? 1 : 0,
        transition: 'opacity 0.8s ease 0.2s'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
          <div style={{
            width: '36px',
            height: '36px',
            background: 'linear-gradient(135deg, #fafafa 0%, #e0e0e0 100%)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span style={{ 
              fontFamily: "'Fraunces', serif", 
              fontSize: '20px', 
              fontWeight: '600', 
              color: '#0a0a0a' 
            }}>K</span>
          </div>
          <span style={{ 
            fontSize: '18px', 
            fontWeight: '600', 
            letterSpacing: '-0.3px',
            color: '#fafafa'
          }}>Kararatlas</span>
        </div>
        
        <div style={{ display: 'flex', gap: '36px', alignItems: 'center' }}>
          <span className="nav-link" onClick={() => onNavigate('features')}>Platform</span>
          <span className="nav-link">Çözümler</span>
          <span className="nav-link">Hakkımızda</span>
        </div>
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span className="nav-link" onClick={() => onNavigate('register')}>Giriş</span>
          <button className="btn-primary magnetic-btn ripple-btn" onClick={() => onNavigate('register')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0a0a0a" strokeWidth="2">
              <path d="M12 5l7 7-7 7" />
              <path d="M5 12h14" />
            </svg>
            30 sn’de demo al
          </button>
        </div>
      </nav>
      
      {/* Main Hero - Split Layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1.1fr',
        minHeight: '100vh',
        gap: '0'
      }}>
        {/* Left Side - Dark */}
        <div style={{
          padding: '160px 50px 80px 70px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          position: 'relative'
        }}>
          {/* Badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '10px',
            marginBottom: '28px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(20px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.3s'
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              background: 'linear-gradient(135deg, #7dd3fc 0%, #38bdf8 100%)',
              borderRadius: '50%',
              animation: 'pulse-subtle 2s ease infinite'
            }} />
            <span style={{ 
              fontSize: '13px', 
              color: 'rgba(255, 255, 255, 0.6)',
              fontWeight: '500',
              letterSpacing: '0.5px'
            }}>
              Türkiye'nin Hukuki Yapay Zekası
            </span>
          </div>
          
          {/* Main Heading */}
          <h1 style={{
            fontFamily: "'Fraunces', serif",
            fontSize: '54px',
            fontWeight: '500',
            lineHeight: '1.18',
            marginBottom: '20px',
            letterSpacing: '-0.8px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(24px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.4s'
          }}>
            Hukuki Araştırmayı
            <br />
            <span style={{ 
              background: 'linear-gradient(135deg, #93c5fd 0%, #c4b5fd 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              Yeniden Tanımlıyoruz
            </span>
          </h1>

          {/* Value prop badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 14px',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '12px',
            marginBottom: '16px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(15px)',
            transition: 'all 0.7s ease 0.45s'
          }}>
            <div style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #93c5fd 0%, #8b7cc9 100%)',
              boxShadow: '0 0 16px rgba(147,197,253,0.4)'
            }} />
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.75)', fontWeight: '600' }}>
              10M+ karar • ~120s yanıt • Atıflı özet
            </span>
          </div>
          
          {/* Description */}
          <p style={{
            fontSize: '16px',
            lineHeight: '1.6',
            color: 'rgba(255, 255, 255, 0.55)',
            marginBottom: '32px',
            maxWidth: '440px',
            fontWeight: '400',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(24px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.5s'
          }}>
            Doğal dilde sorun, atıflı yanıt alın. 10M+ kararı semantik arama, akıllı sıralama ve güvenli altyapı ile dakikalar içinde inceleyin.
          </p>
          
          {/* CTA Buttons */}
          <div style={{
            display: 'flex',
            gap: '12px',
            marginBottom: '52px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(24px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.6s',
            flexWrap: 'wrap'
          }}>
            <button className="btn-primary magnetic-btn ripple-btn" onClick={() => onNavigate('register')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0a0a0a" strokeWidth="2">
                <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
              </svg>
              Hızlı demo al
            </button>
            <button className="btn-secondary magnetic-btn ripple-btn" onClick={() => onNavigate('features')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v5l3 1" />
              </svg>
              Ürün turu
            </button>
          </div>
          
          {/* Stats */}
          <div style={{
            display: 'flex',
            gap: '24px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(16px)',
            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.7s',
            flexWrap: 'wrap'
          }}>
            {[
              { value: statValues[0], label: 'Yargıtay' },
              { value: statValues[1], label: 'Yerel Mahkeme' },
              { value: statValues[2], label: 'İstinaf' }
            ].map((stat, i) => (
              <div key={i} style={{ 
                padding: '12px 18px',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                background: 'rgba(255,255,255,0.03)',
                minWidth: '140px'
              }}>
                <div style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '26px',
                  fontWeight: '500',
                  color: '#fafafa',
                  marginBottom: '6px'
                }}>
                  <span className="stat-count">{formatStat(stat.value || 0, i)}</span>
                  <span style={{
                    marginLeft: '8px',
                    fontSize: '11px',
                    color: 'rgba(147,197,253,0.9)',
                    background: 'rgba(147,197,253,0.12)',
                    padding: '3px 6px',
                    borderRadius: '8px'
                  }}>↑ %12</span>
                </div>
                <div style={{
                  fontSize: '13px',
                  color: 'rgba(255, 255, 255, 0.6)',
                  fontWeight: '600',
                  letterSpacing: '0.3px'
                }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Right Side - Light (Demo Preview) */}
        <div style={{
          background: 'linear-gradient(160deg, #f0f4f8 0%, #e2e8f0 100%)',
          padding: '120px 50px 60px 40px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden'
        }}>
          <div className="light-beam" style={{ pointerEvents: 'none' }} />
          {/* Main Demo Card Container */}
          <div className="hero-demo" style={{
            width: '100%',
            maxWidth: '580px',
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? `translateY(${parallaxY * -0.15}px) scale(1)` : 'translateY(40px) scale(0.95)',
            transition: 'all 1s cubic-bezier(0.4, 0, 0.2, 1) 0.4s',
            padding: '16px',
            zIndex: 1,
            background: 'rgba(255,255,255,0.2)',
            borderRadius: '20px',
            border: '1px solid rgba(0,0,0,0.04)',
            boxShadow: '0 30px 80px rgba(0,0,0,0.15)'
          }}>
            {/* Persona toggles */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '14px',
              justifyContent: 'center',
              position: 'relative',
              zIndex: 10
            }}>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'nowrap' }}>
                {personaLabels.map(p => (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => { setPersona(p.key); setActiveDemo(0); }}
                    style={{
                      padding: '9px 12px',
                      borderRadius: '999px',
                      border: persona === p.key ? `1px solid ${personaColors[p.key]}60` : '1px solid rgba(0,0,0,0.06)',
                      background: persona === p.key 
                        ? `linear-gradient(120deg, ${personaColors[p.key]}20 0%, ${personaColors[p.key]}10 100%)`
                        : '#f7f9fb',
                      color: '#0f172a',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.25s ease',
                      boxShadow: persona === p.key ? `0 10px 25px ${personaColors[p.key]}25` : 'none'
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            {/* Query Card */}
            <div style={{
              background: '#0f172a',
              borderRadius: '16px',
              padding: '22px 24px',
              marginBottom: '14px',
              border: '1px solid rgba(255,255,255,0.06)',
              boxShadow: '0 20px 50px rgba(0,0,0,0.25)',
              color: '#e2e8f0',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                inset: 0,
                background: `radial-gradient(circle at 20% 10%, ${personaColors[persona]}25, transparent 45%), radial-gradient(circle at 80% 80%, rgba(255,255,255,0.1), transparent 50%)`,
                pointerEvents: 'none'
              }} />
              <div style={{
                fontSize: '11px',
                color: 'rgba(226, 232, 240, 0.7)',
                marginBottom: '12px',
                fontWeight: '700',
                letterSpacing: '1px',
                textTransform: 'uppercase'
              }}>Sorgunuz</div>
              
              <div style={{
                fontSize: '16px',
                color: '#e2e8f0',
                lineHeight: '1.65',
                minHeight: '90px',
                fontWeight: '500',
                position: 'relative'
              }}>
                {isLoadingDemo && (
                  <div style={{ position: 'absolute', inset: 0, display: 'grid', gap: '10px' }}>
                    <div style={{ height: '12px', width: '80%', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', animation: 'shimmer 1.3s ease infinite' }} />
                    <div style={{ height: '12px', width: '90%', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', animation: 'shimmer 1.3s ease infinite' }} />
                    <div style={{ height: '12px', width: '70%', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', animation: 'shimmer 1.3s ease infinite' }} />
                  </div>
                )}
                {typingText}
                <span style={{
                  display: 'inline-block',
                  width: '2px',
                  height: '20px',
                  background: '#e2e8f0',
                  marginLeft: '3px',
                  verticalAlign: 'middle',
                  animation: 'blink 1s infinite'
                }} />
              </div>
              
              {/* Referenced decisions - redesigned */}
              {active && (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                  gap: '10px',
                  marginTop: '18px'
                }}>
                  {active.refs.map((ref, i) => (
                    <div
                      key={i}
                      onClick={() => handleRefClick(i)}
                      onMouseEnter={() => setHoveredRef(i)}
                      onMouseLeave={() => setHoveredRef(null)}
                      style={{
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 12px',
                        background: 'rgba(255,255,255,0.04)',
                        border: activeDemo === i ? `1px solid ${personaColors[persona]}60` : '1px solid rgba(255,255,255,0.06)',
                        borderRadius: '10px',
                        fontSize: '12px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        transition: 'transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease',
                        boxShadow: activeDemo === i ? `0 12px 30px ${personaColors[persona]}30` : 'none',
                        transform: activeDemo === i ? 'translateY(-2px)' : 'translateY(0)',
                        color: '#e2e8f0'
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={personaColors[persona]} strokeWidth="1.8">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <path d="M14 2v6h6"/>
                      </svg>
                      <span>{ref.hd}</span>
                      <span style={{ color: 'rgba(226,232,240,0.7)' }}>{ref.no}</span>
                      {hoveredRef === i && (
                        <div style={{
                          position: 'absolute',
                          top: '-44px',
                          left: '0',
                          padding: '8px 10px',
                          background: '#fff',
                          color: '#0f172a',
                          fontSize: '11px',
                          borderRadius: '8px',
                          boxShadow: '0 10px 30px rgba(0,0,0,0.18)',
                          whiteSpace: 'nowrap',
                          border: `1px solid ${personaColors[persona]}40`
                        }}>
                          {ref.info}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Answer Card - redesigned */}
            <div style={{
              background: '#ffffff',
              borderRadius: '16px',
              padding: '24px 26px',
              boxShadow: '0 25px 80px rgba(0, 0, 0, 0.12), 0 10px 30px rgba(0, 0, 0, 0.08)',
              opacity: showAnswer ? 1 : 0,
              transform: showAnswer ? 'translateY(0)' : 'translateY(20px)',
              transition: 'all 0.7s cubic-bezier(0.4, 0, 0.2, 1)'
            }}>
              {isLoadingDemo && (
                <div style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '8px', alignItems: 'center' }}>
                    {progressSteps.map((step, idx) => (
                      <div key={idx} style={{
                        flex: 1,
                        height: '6px',
                        borderRadius: '6px',
                        background: idx <= progressStep ? `linear-gradient(90deg, ${personaColors[persona]}, #0ea5e9)` : 'rgba(0,0,0,0.08)',
                        transition: 'background 0.3s ease'
                      }} />
                    ))}
                  </div>
                  <div style={{ fontSize: '12px', color: 'rgba(0,0,0,0.55)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>{progressSteps[progressStep]?.label || 'Özetleniyor'}</span>
                    <span style={{ fontSize: '11px', color: 'rgba(99,133,181,0.8)' }}>~120s</span>
                  </div>
                </div>
              )}
              {/* AI Summary */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(99, 133, 181, 0.1) 0%, rgba(140, 120, 200, 0.05) 100%)',
                borderLeft: '3px solid rgba(99, 133, 181, 0.5)',
                borderRadius: '0 12px 12px 0',
                padding: '20px 22px',
                marginBottom: '22px'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '12px'
                }}>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    background: `linear-gradient(135deg, ${personaColors[persona]} 0%, #0ea5e9 100%)`,
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
                      <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                      <path d="M2 17l10 5 10-5"/>
                      <path d="M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <span style={{
                    fontSize: '11px',
                    color: '#0f172a',
                    fontWeight: '800',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase'
                  }}>AI Özeti</span>
                  <button
                    onClick={handleCopySummary}
                    style={{
                      marginLeft: 'auto',
                      background: `${personaColors[persona]}15`,
                      border: `1px solid ${personaColors[persona]}40`,
                      color: '#0f172a',
                      fontSize: '11px',
                      padding: '6px 8px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontWeight: 700
                    }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0f172a" strokeWidth="2">
                      <rect x="9" y="9" width="11" height="13" rx="2" />
                      <path d="M5 15V5a2 2 0 012-2h10" />
                    </svg>
                    {copied ? 'Kopyalandı' : 'Kopyala'}
                  </button>
                </div>
                <p style={{
                  fontSize: '14px',
                  color: '#1f2937',
                  lineHeight: '1.75',
                  margin: 0,
                  fontWeight: '500'
                }}>
                  {active?.summary}
                </p>
              </div>
              
              {/* Rule Cards - larger */}
              {active && (
                <div style={{ marginBottom: '18px' }}>
                  <div style={{
                    fontSize: '11px',
                    color: 'rgba(0, 0, 0, 0.45)',
                    marginBottom: '12px',
                    fontWeight: '700',
                    letterSpacing: '0.5px'
                  }}>İlgili Kural Kartları</div>
                  
                  {active.rules.map((card, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '14px 16px',
                      background: `${card.color}08`,
                      marginBottom: '8px',
                      borderRadius: '12px',
                      border: `1px solid ${card.color}30`,
                      transition: 'all 0.3s ease',
                      cursor: 'pointer'
                    }}>
                      <div style={{
                        width: '9px',
                        height: '9px',
                        background: card.color,
                        borderRadius: '50%',
                        boxShadow: `0 0 0 6px ${card.color}15`
                      }} />
                      <span style={{ fontSize: '13px', color: '#111827', fontWeight: '600' }}>{card.title}</span>
                      <span style={{ 
                        marginLeft: 'auto', 
                        fontSize: '11px', 
                        color: 'rgba(0, 0, 0, 0.55)',
                        fontFamily: "'JetBrains Mono', monospace",
                        fontWeight: '600'
                      }}>
                        {card.count} karar
                      </span>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Source Citations */}
              {active && (
                <div style={{
                  display: 'flex',
                  gap: '8px',
                  flexWrap: 'wrap'
                }}>
                  {active.citations.map((cite, i) => (
                    <span key={i} className="source-chip" style={{
                      fontSize: '11px',
                      color: '#0f172a',
                      padding: '7px 10px',
                      background: 'rgba(15, 23, 42, 0.04)',
                      borderRadius: '8px',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontWeight: '600',
                      border: i === activeDemo ? `1px solid ${personaColors[persona]}50` : '1px solid rgba(0,0,0,0.06)',
                      boxShadow: i === activeDemo ? `0 8px 18px ${personaColors[persona]}25` : 'none'
                    }}>
                      {cite}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          
        </div>
      </div>
      
      {/* AI Technology Marquee */}
      <div style={{
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '50px 0',
        background: 'linear-gradient(180deg, rgba(99, 133, 181, 0.03) 0%, transparent 100%)',
        overflow: 'hidden'
      }}>
        <div style={{
          textAlign: 'center',
          marginBottom: '36px'
        }}>
          <div style={{
            fontSize: '12px',
            color: 'rgba(147, 197, 253, 0.8)',
            letterSpacing: '2px',
            textTransform: 'uppercase',
            marginBottom: '10px',
            fontWeight: '600'
          }}>
            Yapay Zeka Altyapısı
          </div>
          <h2 style={{
            fontFamily: "'Fraunces', serif",
            fontSize: '28px',
            fontWeight: '500',
            color: '#fafafa'
          }}>
            Türk Hukuku İçin Özel Geliştirildi
          </h2>
        </div>
        
        {/* Marquee */}
        <div style={{ 
          position: 'relative',
          overflow: 'hidden',
          padding: '10px 0'
        }}>
          {/* Gradient overlays */}
          <div style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: '150px',
            background: 'linear-gradient(90deg, #0a0a0a 0%, transparent 100%)',
            zIndex: 10,
            pointerEvents: 'none'
          }} />
          <div style={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: '150px',
            background: 'linear-gradient(270deg, #0a0a0a 0%, transparent 100%)',
            zIndex: 10,
            pointerEvents: 'none'
          }} />
          
          <div className="marquee-track">
            {[...techItems, ...techItems].map((item, i) => (
              <div
                key={i}
                className="marquee-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  padding: '24px 48px',
                  marginRight: '24px',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '16px',
                  minWidth: '220px',
                  transition: 'all 0.4s ease'
                }}
              >
                <div style={{
                  fontSize: '15px',
                  fontWeight: '600',
                  color: '#fafafa',
                  marginBottom: '6px',
                  textAlign: 'left',
                  width: '100%'
                }}>
                  {item.name}
                </div>
                <div style={{
                  fontSize: '13px',
                  color: 'rgba(255, 255, 255, 0.4)',
                  fontWeight: '400',
                  textAlign: 'left',
                  width: '100%'
                }}>
                  {item.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Features Grid */}
      <div style={{
        padding: '100px 70px'
      }}>
        <div style={{
          maxWidth: '1300px',
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '24px'
        }}>
          {[
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="11" cy="11" r="8"/>
                  <path d="M21 21l-4.35-4.35"/>
                  <path d="M11 8v6M8 11h6"/>
                </svg>
              ),
              title: 'Anlam Bazlı Arama',
              desc: 'Anahtar kelime değil, kavram araması. Ne sormak istediğinizi doğal dilde yazın, sistem anlasın.',
              color: '#6385b5'
            },
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                  <path d="M2 17l10 5 10-5"/>
                  <path d="M2 12l10 5 10-5"/>
                </svg>
              ),
              title: 'Özel Sıralama Modeli',
              desc: 'Türk hukuku için eğitilmiş akıllı sıralama. En alakalı kararlar her zaman en üstte.',
              color: '#8b7cc9'
            },
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                  <path d="M14 2v6h6"/>
                  <path d="M16 13H8M16 17H8M10 9H8"/>
                </svg>
              ),
              title: 'Dilekçe Asistanı',
              desc: 'Emsal kararları otomatik bulup, uygun dilekçe taslağını saniyeler içinde hazırlayın.',
              color: '#5a9a8b'
            }
          ].map((feature, i) => (
            <div 
              key={i}
              className="card-glass"
              style={{
                padding: '40px 36px',
                cursor: 'pointer',
                opacity: isLoaded ? 1 : 0,
                transform: isLoaded ? 'translateY(0) rotate(0deg)' : 'translateY(24px) rotate(-1deg)',
                transition: `all 0.8s cubic-bezier(0.4, 0, 0.2, 1) ${0.1 * i + 0.3}s`
              }}
              onClick={() => onNavigate('features')}
            >
              <div style={{
                width: '56px',
                height: '56px',
                background: `linear-gradient(135deg, ${feature.color}20 0%, ${feature.color}10 100%)`,
                borderRadius: '14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '24px',
                color: feature.color
              }}>
                {feature.icon}
              </div>
              
              <h3 style={{
                fontFamily: "'Fraunces', serif",
                fontSize: '22px',
                fontWeight: '500',
                marginBottom: '12px',
                color: '#fafafa'
              }}>
                {feature.title}
              </h3>
              
              <p style={{
                fontSize: '14px',
                lineHeight: '1.7',
                color: 'rgba(255, 255, 255, 0.45)',
                marginBottom: '24px'
              }}>
                {feature.desc}
              </p>
              
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: 'rgba(255, 255, 255, 0.6)',
                fontSize: '14px',
                fontWeight: '500'
              }}>
                Daha fazla
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Trust Section */}
      <div style={{
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '60px 70px',
        textAlign: 'center',
        background: 'linear-gradient(120deg, rgba(255,255,255,0.02), rgba(99,133,181,0.05))'
      }}>
        <p style={{ 
          fontSize: '12px', 
          color: 'rgba(255, 255, 255, 0.45)', 
          letterSpacing: '2px', 
          textTransform: 'uppercase', 
          marginBottom: '18px',
          fontWeight: '600'
        }}>
          Güven Sinyalleri
        </p>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'center', 
          gap: '18px', 
          alignItems: 'center',
          flexWrap: 'wrap'
        }}>
          {[
            { label: '100+ hukuk bürosu', icon: '🏛️' },
            { label: '10M+ karar', icon: '📚' },
            { label: 'KVKK uyumlu', icon: '🔒' },
            { label: 'Atıflı yanıt', icon: '🔗' }
          ].map((item, i) => (
            <div key={i} style={{ 
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 14px',
              background: 'rgba(255,255,255,0.04)',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.75)',
              fontSize: '14px',
              fontWeight: 600
            }}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Footer */}
      <footer style={{
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '36px 70px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px',
            height: '28px',
            background: '#fafafa',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span style={{ fontFamily: "'Fraunces', serif", fontSize: '14px', fontWeight: '600', color: '#0a0a0a' }}>K</span>
          </div>
          <span style={{ fontSize: '13px', color: 'rgba(255, 255, 255, 0.35)' }}>
            © 2025 Kararatlas. Tüm hakları saklıdır.
          </span>
        </div>
        
        <div style={{ display: 'flex', gap: '28px' }}>
          {['Gizlilik', 'Şartlar', 'Güvenlik', 'İletişim'].map((link, i) => (
            <a key={i} href="#" style={{ 
              fontSize: '13px', 
              color: 'rgba(255, 255, 255, 0.35)', 
              textDecoration: 'none',
              fontWeight: '500',
              transition: 'color 0.3s ease'
            }}>
              {link}
            </a>
          ))}
        </div>
      </footer>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE 2: REGISTER
// ═══════════════════════════════════════════════════════════════════════════════

const RegisterPage = ({ onNavigate }) => {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    organization: '',
    profession: ''
  });
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setTimeout(() => setIsVisible(true), 100);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (step === 1) {
      setStep(2);
    } else {
      setIsLoading(true);
      setTimeout(() => {
        setIsLoading(false);
        alert('Başvurunuz alındı. En kısa sürede sizinle iletişime geçeceğiz.');
      }, 1500);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'grid',
      gridTemplateColumns: '1fr 1.1fr'
    }}>
      {/* Left - Form */}
      <div style={{
        padding: '60px 70px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        position: 'relative'
      }}>
        <div 
          onClick={() => onNavigate('landing')}
          style={{
            position: 'absolute',
            top: '50px',
            left: '70px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'rgba(255, 255, 255, 0.45)',
            fontSize: '14px',
            cursor: 'pointer',
            fontWeight: '500'
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          Ana Sayfa
        </div>
        
        <div style={{ 
          maxWidth: '420px',
          opacity: isVisible ? 1 : 0,
          transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
          transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)'
        }}>
          {/* Logo */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            marginBottom: '50px'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              background: 'linear-gradient(135deg, #fafafa 0%, #e0e0e0 100%)',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
            justifyContent: 'center'
          }}>
              <span style={{ 
                fontFamily: "'Fraunces', serif", 
                fontSize: '22px', 
                fontWeight: '600', 
                color: '#0a0a0a' 
              }}>K</span>
            </div>
            <span style={{ fontSize: '20px', fontWeight: '600' }}>Kararatlas</span>
          </div>
          
          <h1 style={{
            fontFamily: "'Fraunces', serif",
            fontSize: '38px',
            fontWeight: '500',
            marginBottom: '14px',
            letterSpacing: '-0.5px'
          }}>
            {step === 1 ? 'Hesap Oluşturun' : 'Kurum Bilgileri'}
          </h1>
          
          <p style={{ 
            fontSize: '16px', 
            color: 'rgba(255, 255, 255, 0.45)', 
            marginBottom: '36px',
            lineHeight: '1.6'
          }}>
            {step === 1 
              ? 'Ücretsiz deneme hesabınızı oluşturun. Kredi kartı gerekmez.'
              : 'Son adım - kurum ve meslek bilgilerinizi ekleyin.'}
          </p>
          
          {/* Progress */}
          <div style={{
            display: 'flex',
            gap: '10px',
            marginBottom: '36px'
          }}>
            {[1, 2].map((s) => (
              <div key={s} style={{
                width: s <= step ? '56px' : '28px',
                height: '4px',
                background: s <= step 
                  ? 'linear-gradient(90deg, #6385b5 0%, #8b7cc9 100%)' 
                  : 'rgba(255,255,255,0.1)',
                borderRadius: '2px',
                transition: 'all 0.4s ease'
              }} />
            ))}
          </div>
          
          <form onSubmit={handleSubmit}>
            {step === 1 ? (
              <>
                <div style={{ marginBottom: '22px' }}>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '13px', 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    marginBottom: '10px',
                    fontWeight: '500'
                  }}>
                    Ad Soyad
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="Adınız ve soyadınız"
                    value={formData.fullName}
                    onChange={(e) => setFormData({...formData, fullName: e.target.value})}
                    required
                  />
                </div>
                
                <div style={{ marginBottom: '22px' }}>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '13px', 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    marginBottom: '10px',
                    fontWeight: '500'
                  }}>
                    E-posta
                  </label>
                  <input
                    type="email"
                    className="input-field"
                    placeholder="ornek@kurumsal.com"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    required
                  />
                </div>
                
                <div style={{ marginBottom: '36px' }}>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '13px', 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    marginBottom: '10px',
                    fontWeight: '500'
                  }}>
                    Şifre
                  </label>
                  <input
                    type="password"
                    className="input-field"
                    placeholder="En az 8 karakter"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                    minLength={8}
                  />
                </div>
              </>
            ) : (
              <>
                <div style={{ marginBottom: '22px' }}>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '13px', 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    marginBottom: '10px',
                    fontWeight: '500'
                  }}>
                    Kurum / Şirket
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="Kurum veya şirket adı"
                    value={formData.organization}
                    onChange={(e) => setFormData({...formData, organization: e.target.value})}
                    required
                  />
                </div>
                
                <div style={{ marginBottom: '36px' }}>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '13px', 
                    color: 'rgba(255, 255, 255, 0.5)', 
                    marginBottom: '10px',
                    fontWeight: '500'
                  }}>
                    Meslek
                  </label>
                  <select
                    className="input-field"
                    value={formData.profession}
                    onChange={(e) => setFormData({...formData, profession: e.target.value})}
                    required
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="">Seçiniz</option>
                    <option value="lawyer">Avukat</option>
                    <option value="judge">Hakim / Savcı</option>
                    <option value="academic">Akademisyen</option>
                    <option value="student">Hukuk Öğrencisi</option>
                    <option value="corporate">Şirket Hukuk Müşaviri</option>
                    <option value="other">Diğer</option>
                  </select>
                </div>
              </>
            )}
            
            <button
              type="submit"
              className="btn-primary"
              disabled={isLoading}
              style={{
                width: '100%',
                justifyContent: 'center',
                padding: '16px',
                fontSize: '15px',
                opacity: isLoading ? 0.7 : 1
              }}
            >
              {isLoading ? 'İşleniyor...' : step === 1 ? 'Devam Et' : 'Hesabı Oluştur'}
            </button>
            
            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(1)}
                style={{
                  width: '100%',
                  marginTop: '14px',
                  background: 'transparent',
                  border: 'none',
                  color: 'rgba(255, 255, 255, 0.45)',
                  fontSize: '14px',
                  cursor: 'pointer',
                  padding: '14px',
                  fontWeight: '500'
                }}
              >
                ← Geri
              </button>
            )}
          </form>
          
          <div style={{
            marginTop: '40px',
            paddingTop: '40px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)'
          }}>
            <p style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.45)' }}>
              Zaten hesabınız var mı?{' '}
              <a href="#" style={{ color: '#93c5fd', textDecoration: 'none', fontWeight: '500' }}>
                Giriş Yapın
              </a>
            </p>
          </div>
        </div>
      </div>
      
      {/* Right - Visual */}
      <div style={{
        background: 'linear-gradient(160deg, #f0f4f8 0%, #e2e8f0 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 60px',
        position: 'relative'
      }}>
        <div style={{
          maxWidth: '460px',
          opacity: isVisible ? 1 : 0,
          transform: isVisible ? 'translateX(0)' : 'translateX(30px)',
          transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.2s'
        }}>
          <div style={{
            fontSize: '12px',
            color: 'rgba(0, 0, 0, 0.45)',
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            marginBottom: '16px',
            fontWeight: '600'
          }}>
            Platform
          </div>
          
          <h2 style={{
            fontFamily: "'Fraunces', serif",
            fontSize: '42px',
            fontWeight: '500',
            color: '#1a1a1a',
            lineHeight: '1.2',
            marginBottom: '24px'
          }}>
            Hukuki Asistanınız
            <br />
            Her Zaman Yanınızda
          </h2>
          
          <p style={{
            fontSize: '16px',
            lineHeight: '1.7',
            color: 'rgba(0, 0, 0, 0.55)',
            marginBottom: '44px'
          }}>
            Karmaşık hukuki araştırma görevlerini doğal dille 
            sorgulayın. Türk hukuku için özel geliştirilmiş yapay zeka ile 
            saatlerce süren işleri dakikalara indirin.
          </p>
          
          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {[
              '10M+ mahkeme kararına anında erişim',
              'Özel eğitilmiş Türk hukuku modeli',
              'Otomatik özet ve kaynak atıfları',
              'Dilekçe taslak asistanı'
            ].map((feature, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                opacity: isVisible ? 1 : 0,
                transform: isVisible ? 'translateX(0)' : 'translateX(20px)',
                transition: `all 0.6s ease ${0.4 + i * 0.1}s`
              }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  background: 'linear-gradient(135deg, rgba(99, 133, 181, 0.2) 0%, rgba(140, 120, 200, 0.15) 100%)',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6385b5" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <span style={{ fontSize: '15px', color: '#2a2a2a', fontWeight: '500' }}>{feature}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Decorative */}
        <div style={{
          position: 'absolute',
          bottom: '50px',
          right: '50px',
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          background: '#ffffff',
          padding: '16px 20px',
          borderRadius: '12px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.08)'
        }}>
          <div style={{
            width: '44px',
            height: '44px',
            background: 'linear-gradient(135deg, #6385b5 0%, #8b7cc9 100%)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '15px',
            fontWeight: '600'
          }}>AK</div>
          <div>
            <div style={{ fontSize: '14px', fontWeight: '600', color: '#1a1a1a' }}>Av. Ahmet Kaya</div>
            <div style={{ fontSize: '12px', color: 'rgba(0,0,0,0.45)' }}>&quot;Araştırma sürem %70 azaldı.&quot;</div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE 3: FEATURES
// ═══════════════════════════════════════════════════════════════════════════════

const FeaturesPage = ({ onNavigate }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setTimeout(() => setIsVisible(true), 100);
  }, []);

  const sections = [
    {
      label: 'Bilgi Tabanı',
      title: 'Hızlı Araştırma,\nGüvenilir Sonuçlar',
      description: 'Yargıtay, İstinaf ve yerel mahkeme kararlarına doğal dilde soru sorun. Her yanıt kaynak atıflı.',
      visual: 'search'
    },
    {
      label: 'Asistan',
      title: 'Uzmanlığınıza\nÖzel Asistan',
      description: 'Karmaşık hukuki görevleri doğal dilde delege edin. Türk hukuku için özel eğitilmiş.',
      visual: 'assistant'
    },
    {
      label: 'Dosya Deposu',
      title: 'Güvenli Proje\nÇalışma Alanları',
      description: 'Binlerce belgeyi yükleyin ve yapay zeka ile analiz edin. KVKK uyumlu güvenlik.',
      visual: 'vault'
    }
  ];

  const renderVisual = (type) => {
    switch(type) {
      case 'search':
        return (
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 25px 80px rgba(0,0,0,0.12)',
            width: '100%',
            maxWidth: '440px'
          }}>
            <div style={{
              padding: '16px 20px',
              background: 'rgba(0,0,0,0.02)',
              border: '1px solid rgba(0,0,0,0.08)',
              borderRadius: '10px',
              fontSize: '15px',
              color: '#1a1a1a',
              marginBottom: '20px'
            }}>
              Hukuki sorgunuzu yazın...
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {[
                { name: 'Yargıtay', count: '9.5M' },
                { name: 'İstinaf', count: '200K' },
                { name: 'Yerel Mahkeme', count: '500K' }
              ].map((source, i) => (
                <div key={i} style={{
                  padding: '12px 18px',
                  background: 'linear-gradient(135deg, rgba(99, 133, 181, 0.1) 0%, rgba(99, 133, 181, 0.05) 100%)',
                  border: '1px solid rgba(99, 133, 181, 0.2)',
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}>
                  <span style={{ fontSize: '13px', fontWeight: '600', color: '#2a2a2a' }}>{source.name}</span>
                  <span style={{ fontSize: '11px', color: 'rgba(0,0,0,0.45)', fontFamily: "'JetBrains Mono', monospace" }}>{source.count} karar</span>
                </div>
              ))}
            </div>
          </div>
        );
      case 'assistant':
        return (
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 25px 80px rgba(0,0,0,0.12)',
            width: '100%',
            maxWidth: '440px'
          }}>
            <div style={{ fontSize: '13px', color: 'rgba(0,0,0,0.45)', marginBottom: '12px', fontWeight: '600' }}>Sorgunuz</div>
            <p style={{ fontSize: '15px', color: '#1a1a1a', lineHeight: '1.6', marginBottom: '20px' }}>
              Müvekkilim işyeri kirasının TÜFE oranında artırılmasına itiraz ediyor. 
              Emsal kararları bulup savunma stratejisi önerir misin?
            </p>
            <button style={{
              width: '100%',
              padding: '14px',
              background: '#1a1a1a',
              color: '#fff',
              border: 'none',
              borderRadius: '10px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer'
            }}>
              Kararatlas'a Sor
            </button>
          </div>
        );
      case 'vault':
        return (
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            padding: '28px',
            boxShadow: '0 25px 80px rgba(0,0,0,0.12)',
            width: '100%',
            maxWidth: '440px'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Dosya', 'Tarih', 'Durum'].map((h, i) => (
                    <th key={i} style={{ 
                      textAlign: 'left', 
                      padding: '10px 14px', 
                      fontSize: '12px', 
                      fontWeight: '600', 
                      color: '#1a1a1a', 
                      borderBottom: '1px solid rgba(0,0,0,0.08)' 
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[1,2,3,4].map((_, i) => (
                  <tr key={i}>
                    <td style={{ padding: '12px 14px' }}><div style={{ width: '80px', height: '10px', background: 'rgba(0,0,0,0.06)', borderRadius: '5px' }} /></td>
                    <td style={{ padding: '12px 14px' }}><div style={{ width: '55px', height: '10px', background: 'rgba(0,0,0,0.06)', borderRadius: '5px' }} /></td>
                    <td style={{ padding: '12px 14px' }}><div style={{ width: '45px', height: '10px', background: 'rgba(99, 133, 181, 0.2)', borderRadius: '5px' }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div style={{ minHeight: '100vh' }}>
      {/* Navigation */}
      <nav style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        padding: '20px 48px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 100,
        background: 'rgba(10, 10, 10, 0.95)',
        backdropFilter: 'blur(20px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => onNavigate('landing')}>
          <div style={{
            width: '36px',
            height: '36px',
            background: 'linear-gradient(135deg, #fafafa 0%, #e0e0e0 100%)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span style={{ fontFamily: "'Fraunces', serif", fontSize: '20px', fontWeight: '600', color: '#0a0a0a' }}>K</span>
          </div>
          <span style={{ fontSize: '18px', fontWeight: '600' }}>Kararatlas</span>
        </div>
        
        <div style={{ display: 'flex', gap: '36px', alignItems: 'center' }}>
          <span className="nav-link" style={{ color: 'rgba(255,255,255,0.9)' }}>Platform</span>
          <span className="nav-link">Çözümler</span>
          <span className="nav-link">Hakkımızda</span>
        </div>
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span className="nav-link">Giriş</span>
          <button className="btn-primary ripple-btn" onClick={() => onNavigate('register')}>Demo Talep Et</button>
        </div>
      </nav>
      
      {/* Sections */}
      {sections.map((section, index) => (
        <div
          key={index}
          style={{
            minHeight: '100vh',
            display: 'grid',
            gridTemplateColumns: '1fr 1.1fr'
          }}
        >
          <div style={{
            background: index % 2 === 0 ? '#0a0a0a' : '#0f0f0f',
            padding: '160px 70px 80px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center'
          }}>
            <div style={{
              maxWidth: '480px',
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
              transition: `all 0.8s cubic-bezier(0.4, 0, 0.2, 1) ${index * 0.1}s`
            }}>
              <div style={{
                fontSize: '12px',
                color: 'rgba(147, 197, 253, 0.8)',
                letterSpacing: '1.5px',
                textTransform: 'uppercase',
                marginBottom: '20px',
                fontWeight: '600'
              }}>
                {section.label}
              </div>
              
              <h2 style={{
                fontFamily: "'Fraunces', serif",
                fontSize: '46px',
                fontWeight: '500',
                lineHeight: '1.12',
                marginBottom: '24px',
                whiteSpace: 'pre-line',
                color: '#fafafa'
              }}>
                {section.title}
              </h2>
              
              <p style={{
                fontSize: '17px',
                lineHeight: '1.7',
                color: 'rgba(255, 255, 255, 0.5)',
                marginBottom: '36px'
              }}>
                {section.description}
              </p>
              
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '10px',
                color: 'rgba(255, 255, 255, 0.7)',
                fontSize: '15px',
                cursor: 'pointer',
                fontWeight: '500'
              }}>
                Daha Fazla
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </div>
            </div>
          </div>
          
          <div style={{
            background: 'linear-gradient(160deg, #f0f4f8 0%, #e2e8f0 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '80px 60px'
          }}>
            <div style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0) scale(1)' : 'translateY(30px) scale(0.95)',
              transition: `all 0.8s cubic-bezier(0.4, 0, 0.2, 1) ${index * 0.1 + 0.2}s`
            }}>
              {renderVisual(section.visual)}
            </div>
          </div>
        </div>
      ))}
      
      {/* CTA */}
      <div style={{
        background: '#0a0a0a',
        padding: '100px 70px',
        textAlign: 'center',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)'
      }}>
        <h2 style={{
          fontFamily: "'Fraunces', serif",
          fontSize: '42px',
          fontWeight: '500',
          marginBottom: '18px',
          color: '#fafafa'
        }}>
          Hemen Başlayın
        </h2>
        <p style={{
          fontSize: '17px',
          color: 'rgba(255, 255, 255, 0.45)',
          marginBottom: '40px'
        }}>
          Ücretsiz demo talep edin. Ekibimiz sizinle iletişime geçecek.
        </p>
        
        <div style={{ display: 'flex', gap: '14px', justifyContent: 'center' }}>
          <button className="btn-primary ripple-btn" onClick={() => onNavigate('register')}>Demo Talep Et</button>
          <button className="btn-secondary ripple-btn">Ürün Turu</button>
        </div>
      </div>
      
      {/* Footer */}
      <footer style={{
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '36px 70px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px',
            height: '28px',
            background: '#fafafa',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span style={{ fontFamily: "'Fraunces', serif", fontSize: '14px', fontWeight: '600', color: '#0a0a0a' }}>K</span>
          </div>
          <span style={{ fontSize: '13px', color: 'rgba(255, 255, 255, 0.35)' }}>© 2025 Kararatlas</span>
        </div>
        
        <div style={{ display: 'flex', gap: '28px' }}>
          {['Gizlilik', 'Şartlar', 'İletişim'].map((link, i) => (
            <a key={i} href="#" style={{ fontSize: '13px', color: 'rgba(255, 255, 255, 0.35)', textDecoration: 'none', fontWeight: '500' }}>{link}</a>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default KararatlasApp;
