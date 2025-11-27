import React, { useMemo, useState, useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import HighlightExtension from "@tiptap/extension-highlight";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Bold, Italic, Underline as IconUnderline,
  AlignLeft, AlignCenter, AlignRight, List, ListOrdered, 
  Highlighter, Undo2, Redo2,
  FileText, Users, Scale, Gavel, ScrollText, 
  Download, Sparkles, ChevronDown, Plus, Trash2,
  AlertCircle, CheckCircle2, Clock, FileType, Minimize2, Maximize2, Info
} from "lucide-react";

// --- Sabitler ve Veri Yapıları ---

const PETITION_TYPES = [
  { value: "dava_dilekcesi", label: "Dava Dilekçesi", icon: Scale },
  { value: "cevap_dilekcesi", label: "Cevap Dilekçesi", icon: FileText },
  { value: "istinaf", label: "İstinaf Başvurusu", icon: ScrollText },
  { value: "suc_duyurusu", label: "Suç Duyurusu", icon: Gavel },
];

const ROLE_OPTIONS = [
  { value: "davaci", label: "Davacı" },
  { value: "davali", label: "Davalı" },
  { value: "davaci_vekili", label: "Davacı Vekili" },
  { value: "davali_vekili", label: "Davalı Vekili" },
];

const defaultState = () => ({
  petition_type: "dava_dilekcesi",
  court: "ANKARA NÖBETÇİ ASLİYE HUKUK MAHKEMESİ",
  subject: "Fazlaya ilişkin haklarımız saklı kalmak kaydıyla...",
  legal_basis: "TBK, HMK ve ilgili mevzuat",
  parties: [
    { role: "davaci", name: "", tc_id: "", address: "" },
    { role: "davali", name: "", tc_id: "", address: "" },
  ],
  facts: [
    { summary: "", evidence_refs: [] },
  ],
  requests: [""],
  evidence: [
    { label: "Ek-1", description: "" },
  ],
});

// --- UI Bileşenleri ---

const SectionHeader = ({ title, icon: Icon, isOpen, onClick }) => (
  <button 
    onClick={onClick}
    className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 border-b border-slate-200 transition-colors text-left"
  >
    <div className="flex items-center gap-2 text-slate-700 font-semibold text-sm">
      <Icon size={16} className="text-brand-600" />
      {title}
    </div>
    <ChevronDown size={16} className={`text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} />
  </button>
);

const InputGroup = ({ label, children, className }) => (
  <div className={`mb-3 ${className || ""}`}>
    <label className="block text-xs font-medium text-slate-500 mb-1.5 uppercase tracking-wide">{label}</label>
    {children}
  </div>
);

const ToolButton = ({ icon: Icon, onClick, active, title }) => (
  <button
    onClick={onClick}
    title={title}
    className={`p-1.5 rounded-md transition-all duration-200 ${
      active 
        ? "bg-brand-100 text-brand-700 shadow-sm" 
        : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
    }`}
  >
    <Icon size={18} strokeWidth={2.5} />
  </button>
);

// --- Ana Uygulama ---

export default function App() {
  // Debug log
  console.log("App rendering started");

  // State
  const [form, setForm] = useState(defaultState);
  const [activeSection, setActiveSection] = useState("general");
  const [loading, setLoading] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  // Env check
  const apiUrl = "http://localhost:9000/generate"; // Hardcode for safety initially

  // Tiptap Editör Kurulumu
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ 
        heading: { levels: [1, 2, 3] },
        history: { depth: 100 }
      }),
      Underline,
      Link.configure({ openOnClick: false, autolink: true }),
      HighlightExtension.configure({ multicolor: true }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({
        placeholder: "Dilekçe metni burada oluşturulacak...",
      }),
    ],
    content: "",
    onUpdate: () => {
      setLastSaved("Kaydedilmedi...");
    },
  });

  // LocalStorage - Auto Save
  useEffect(() => {
    const savedForm = localStorage.getItem("legal-form-draft");
    if (savedForm) {
      try {
        setForm(JSON.parse(savedForm));
      } catch (e) { console.error("Draft load failed", e); }
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      localStorage.setItem("legal-form-draft", JSON.stringify(form));
      if (editor && !editor.isEmpty) {
        localStorage.setItem("legal-editor-content", editor.getHTML());
      }
      setLastSaved(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }, 2000);
    return () => clearTimeout(timer);
  }, [form, editor?.state.doc.content]);


  // Form İşleyicileri
  const updateField = (key, value) => setForm(f => ({ ...f, [key]: value }));
  
  const updateItem = (listName, idx, patch) => {
    setForm(f => {
      const list = [...f[listName]];
      list[idx] = { ...list[idx], ...patch };
      return { ...f, [listName]: list };
    });
  };

  const addItem = (listName, initialItem) => {
    setForm(f => ({ ...f, [listName]: [...f[listName], initialItem] }));
  };

  const removeItem = (listName, idx) => {
    setForm(f => ({ ...f, [listName]: f[listName].filter((_, i) => i !== idx) }));
  };

  // API Generate
  const handleGenerate = async () => {
    setLoading(true);
    try {
      const payload = {
        ...form,
        legal_basis: form.legal_basis.split(",").map(s => s.trim()).filter(Boolean),
      };

      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      if (editor && data.html) {
        editor.commands.setContent(data.html);
      }
      setWarnings(data.qa_warnings || []);
    } catch (err) {
      alert("Hata: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    if(confirm("Tüm veriler silinecek. Emin misiniz?")) {
      setForm(defaultState());
      editor?.commands.clearContent();
      localStorage.removeItem("legal-form-draft");
    }
  };

  // Render Check
  if (!editor) {
    return <div className="flex items-center justify-center h-screen">Editör Yükleniyor...</div>;
  }

  return (
    <div className="flex h-screen w-full bg-[#F6F8FA] overflow-hidden font-sans text-slate-900">
      
      {/* SOL PANEL - Sidebar */}
      <aside className="w-[400px] flex flex-col border-r border-slate-200 bg-white shadow-lg z-10 h-full shrink-0">
        
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-100 bg-white flex items-center justify-between">
          <div className="flex items-center gap-2 text-brand-700">
            <div className="bg-brand-600 text-white p-1.5 rounded-lg">
              <Scale size={20} />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-tight">Legal Studio</h1>
              <p className="text-xs text-slate-500 font-medium">AI Destekli Dilekçe Editörü</p>
            </div>
          </div>
        </div>

        {/* Scrollable Form Area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          
          {/* Bölüm: Genel Bilgiler */}
          <div className="border-b border-slate-100">
            <SectionHeader 
              title="Genel Bilgiler" 
              icon={FileText} 
              isOpen={activeSection === "general"} 
              onClick={() => setActiveSection(activeSection === "general" ? "" : "general")} 
            />
            {activeSection === "general" && (
              <div className="p-4 space-y-4 animate-in slide-in-from-top-2 duration-200">
                <InputGroup label="Dilekçe Türü">
                  <select 
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none transition-all"
                    value={form.petition_type}
                    onChange={(e) => updateField("petition_type", e.target.value)}
                  >
                    {PETITION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </InputGroup>
                
                <InputGroup label="Mahkeme / Merci">
                  <input 
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 outline-none"
                    value={form.court}
                    onChange={(e) => updateField("court", e.target.value)}
                    placeholder="Örn: Ankara 1. Asliye Hukuk Mahkemesi"
                  />
                </InputGroup>

                <InputGroup label="Konu (Özet)">
                  <textarea 
                    rows={3}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 outline-none resize-none"
                    value={form.subject}
                    onChange={(e) => updateField("subject", e.target.value)}
                  />
                </InputGroup>

                 <InputGroup label="Hukuki Sebepler">
                  <input 
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 outline-none"
                    value={form.legal_basis}
                    onChange={(e) => updateField("legal_basis", e.target.value)}
                    placeholder="TMK, TBK, HMK..."
                  />
                </InputGroup>
              </div>
            )}
          </div>

          {/* Bölüm: Taraflar */}
          <div className="border-b border-slate-100">
            <SectionHeader 
              title={`Taraflar (${form.parties.length})`} 
              icon={Users} 
              isOpen={activeSection === "parties"} 
              onClick={() => setActiveSection(activeSection === "parties" ? "" : "parties")} 
            />
            {activeSection === "parties" && (
              <div className="p-3 bg-slate-50/50 space-y-3 animate-in slide-in-from-top-2">
                {form.parties.map((p, idx) => (
                  <div key={idx} className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm relative group">
                    <button 
                      onClick={() => removeItem("parties", idx)}
                      className="absolute top-2 right-2 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 size={14} />
                    </button>
                    <div className="grid grid-cols-2 gap-2 mb-2">
                      <select 
                        className="bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-xs font-medium"
                        value={p.role}
                        onChange={(e) => updateItem("parties", idx, { role: e.target.value })}
                      >
                        {ROLE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                      <input 
                        placeholder="TCKN / VKN"
                        className="bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-xs"
                        value={p.tc_id}
                        onChange={(e) => updateItem("parties", idx, { tc_id: e.target.value })}
                      />
                    </div>
                    <input 
                      placeholder="Ad Soyad / Unvan"
                      className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-sm mb-2 font-medium"
                      value={p.name}
                      onChange={(e) => updateItem("parties", idx, { name: e.target.value })}
                    />
                    <input 
                      placeholder="Adres"
                      className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-xs text-slate-600"
                      value={p.address}
                      onChange={(e) => updateItem("parties", idx, { address: e.target.value })}
                    />
                  </div>
                ))}
                <button 
                  onClick={() => addItem("parties", { role: "davali", name: "", tc_id: "", address: "" })}
                  className="w-full py-2 border border-dashed border-brand-300 text-brand-600 rounded-lg text-xs font-medium hover:bg-brand-50 flex items-center justify-center gap-1 transition-colors"
                >
                  <Plus size={14} /> Taraf Ekle
                </button>
              </div>
            )}
          </div>

           {/* Bölüm: Olgular */}
           <div className="border-b border-slate-100">
            <SectionHeader 
              title={`Olgular ve Olaylar (${form.facts.length})`} 
              icon={Info} 
              isOpen={activeSection === "facts"} 
              onClick={() => setActiveSection(activeSection === "facts" ? "" : "facts")} 
            />
            {activeSection === "facts" && (
              <div className="p-3 bg-slate-50/50 space-y-3 animate-in slide-in-from-top-2">
                {form.facts.map((f, idx) => (
                  <div key={idx} className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm relative group">
                    <button 
                      onClick={() => removeItem("facts", idx)}
                      className="absolute top-2 right-2 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 size={14} />
                    </button>
                    <textarea 
                      rows={2}
                      placeholder="Olay örgüsünü açıklayan bir cümle..."
                      className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-2 text-sm mb-2 resize-none"
                      value={f.summary}
                      onChange={(e) => updateItem("facts", idx, { summary: e.target.value })}
                    />
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase">Deliller:</span>
                      <input 
                        placeholder="Örn: Ek-1, Tanık"
                        className="flex-1 bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs"
                        value={f.evidence_refs?.join(", ") || ""}
                        onChange={(e) => updateItem("facts", idx, { evidence_refs: e.target.value.split(",").map(s=>s.trim()) })}
                      />
                    </div>
                  </div>
                ))}
                <button 
                  onClick={() => addItem("facts", { summary: "", evidence_refs: [] })}
                  className="w-full py-2 border border-dashed border-brand-300 text-brand-600 rounded-lg text-xs font-medium hover:bg-brand-50 flex items-center justify-center gap-1"
                >
                  <Plus size={14} /> Olgu Ekle
                </button>
              </div>
            )}
          </div>

          {/* Bölüm: Deliller */}
          <div className="border-b border-slate-100">
            <SectionHeader 
              title={`Deliller (${form.evidence.length})`} 
              icon={FileType} 
              isOpen={activeSection === "evidence"} 
              onClick={() => setActiveSection(activeSection === "evidence" ? "" : "evidence")} 
            />
            {activeSection === "evidence" && (
              <div className="p-3 bg-slate-50/50 space-y-3 animate-in slide-in-from-top-2">
                {form.evidence.map((e, idx) => (
                  <div key={idx} className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm flex items-start gap-2 relative group">
                     <button 
                      onClick={() => removeItem("evidence", idx)}
                      className="absolute top-1/2 -translate-y-1/2 right-2 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 size={14} />
                    </button>
                    <div className="w-16 shrink-0">
                       <input 
                        className="w-full bg-slate-100 border border-slate-200 rounded px-2 py-1.5 text-xs font-bold text-center"
                        value={e.label}
                        onChange={(evt) => updateItem("evidence", idx, { label: evt.target.value })}
                      />
                    </div>
                    <input 
                      className="flex-1 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 text-sm"
                      placeholder="Delil açıklaması..."
                      value={e.description}
                      onChange={(evt) => updateItem("evidence", idx, { description: evt.target.value })}
                    />
                  </div>
                ))}
                 <button 
                  onClick={() => addItem("evidence", { label: `Ek-${form.evidence.length + 1}`, description: "" })}
                  className="w-full py-2 border border-dashed border-brand-300 text-brand-600 rounded-lg text-xs font-medium hover:bg-brand-50 flex items-center justify-center gap-1"
                >
                  <Plus size={14} /> Delil Ekle
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar Footer / Actions */}
        <div className="p-4 border-t border-slate-200 bg-slate-50">
          {warnings.length > 0 && (
            <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 flex items-start gap-2">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <div>
                <span className="font-bold block mb-1">{warnings.length} Uyarı Mevcut:</span>
                <ul className="list-disc pl-4 space-y-0.5 opacity-80">
                  {warnings.slice(0,2).map((w, i) => <li key={i}>{w}</li>)}
                  {warnings.length > 2 && <li>+{warnings.length - 2} diğer...</li>}
                </ul>
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <button onClick={handleReset} className="flex-1 px-4 py-2.5 border border-slate-300 text-slate-600 rounded-lg text-sm font-semibold hover:bg-slate-100 transition-colors">
              Temizle
            </button>
            <button 
              onClick={handleGenerate}
              disabled={loading}
              className="flex-[2] px-4 py-2.5 bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white rounded-lg text-sm font-semibold shadow-sm shadow-brand-200 flex items-center justify-center gap-2 transition-all disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Üretiliyor...
                </>
              ) : (
                <>
                  <Sparkles size={16} /> Taslak Oluştur
                </>
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* SAĞ PANEL - Editör Alanı */}
      <main className="flex-1 flex flex-col h-full relative bg-slate-100/50">
        
        {/* Top Bar */}
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm z-10 shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
               <span className="text-xs font-medium text-slate-400">Belge Durumu</span>
               <span className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                 {lastSaved ? <CheckCircle2 size={14} className="text-green-500" /> : <Clock size={14} className="text-slate-400" />}
                 {lastSaved ? `Kaydedildi (${lastSaved})` : "Bekleniyor..."}
               </span>
            </div>
          </div>

          {/* Toolbar */}
          {editor && (
            <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200 mx-4">
              <ToolButton icon={Undo2} onClick={() => editor.chain().focus().undo().run()} title="Geri Al" />
              <ToolButton icon={Redo2} onClick={() => editor.chain().focus().redo().run()} title="İleri Al" />
              <div className="w-px h-5 bg-slate-300 mx-1" />
              <ToolButton icon={Bold} active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} />
              <ToolButton icon={Italic} active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} />
              <ToolButton icon={IconUnderline} active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} />
              <ToolButton icon={Highlighter} active={editor.isActive('highlight')} onClick={() => editor.chain().focus().toggleHighlight().run()} />
              <div className="w-px h-5 bg-slate-300 mx-1" />
              <ToolButton icon={AlignLeft} active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} />
              <ToolButton icon={AlignCenter} active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} />
              <ToolButton icon={AlignRight} active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} />
              <div className="w-px h-5 bg-slate-300 mx-1" />
              <ToolButton icon={List} active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} />
              <ToolButton icon={ListOrdered} active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} />
            </div>
          )}

          <div className="flex items-center gap-3">
            <button className="text-slate-500 hover:text-slate-700" title="Tam Ekran" onClick={() => setIsPreviewMode(!isPreviewMode)}>
              {isPreviewMode ? <Minimize2 size={20} /> : <Maximize2 size={20} />}
            </button>
            <button 
              onClick={() => window.print()}
              className="bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors shadow-md"
            >
              <Download size={16} /> İndir / Yazdır
            </button>
          </div>
        </header>

        {/* Editor Canvas */}
        <div className="flex-1 overflow-y-auto p-8 flex justify-center bg-[#F0F2F5] cursor-text" onClick={() => editor?.chain().focus().run()}>
          <div className={`bg-white shadow-page transition-all duration-300 ${isPreviewMode ? "w-[210mm] scale-110" : "w-[210mm]"} min-h-[297mm] p-[25mm] rounded-sm`}>
            <EditorContent editor={editor} />
          </div>
        </div>
      </main>
    </div>
  );
}
