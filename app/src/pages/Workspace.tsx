import { useState, useRef, useEffect } from "react";
import { FileText, Loader2, Mic, FileSearch, CornerDownRight, ArrowRight } from "lucide-react";
import { Button } from "../components/ui/Button";
import { sendChatMessage } from "../lib/api";
import { getTranslation } from "../lib/translations";
import type { SupportedLanguage } from "../lib/translations";
import type { ProcessedDocument, ChatMessage, ChatResponse } from "../lib/api";

interface WorkspaceProps {
  document: ProcessedDocument;
  onBack: () => void;
  language: string;
  isTranslating?: boolean;
}

interface UIMessage extends ChatMessage {
  id: string;
  responseMeta?: ChatResponse;
}

export function Workspace({ document, onBack, language, isTranslating = false }: WorkspaceProps) {
  const intel = document.intelligence;
  const t = (key: string) => getTranslation(key, language as SupportedLanguage);
  
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<any>(null);

  const [activeEvidence, setActiveEvidence] = useState<{
    claim: string;
    evidence: string;
    source: string;
  } | null>(null);

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      
      if (language === "Hindi" || language === "Hinglish") {
        recognition.lang = 'hi-IN';
      } else {
        recognition.lang = 'en-US';
      }

      recognition.onstart = () => setIsRecording(true);
      
      recognition.onresult = (event: any) => {
        let finalTranscript = '';
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setInputValue(finalTranscript);
          handleAsk(finalTranscript);
        } else if (interimTranscript) {
          setInputValue(interimTranscript);
        }
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
    }
  }, [language]);

  const toggleRecording = () => {
    if (isRecording) {
      recognitionRef.current?.stop();
    } else {
      setInputValue("");
      recognitionRef.current?.start();
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (!isLoading && messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
      scrollToBottom();
    }
  }, [messages, isLoading]);

  const handleAsk = async (text: string = inputValue) => {
    if (!text.trim() || isLoading) return;

    const userMessage: UIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      let docContext = "";
      if (document.intelligence) {
        docContext = JSON.stringify(document.intelligence);
      } else if (document.sections && document.sections.length > 0) {
        docContext = document.sections.map(s => `Page ${s.page_number}: ${s.content}`).join("\n\n");
      }

      const history = messages.map(m => ({ role: m.role, content: m.content }));

      const response = await sendChatMessage({
        message: userMessage.content,
        history,
        document_context: docContext,
        language
      });

      const assistantMessage: UIMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        responseMeta: response
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: UIMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I'm sorry, I couldn't process that right now.\n\nReason: ${error.message || t("error.network")}`,
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-neutral-100 font-sans text-neutral-900">
      
      {/* Evidence Drawer Modal */}
      {activeEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-primary-900/40 backdrop-blur-sm animate-fade-in pr-4 pb-4 pt-4">
          <div className="bg-neutral-50 shadow-2xl h-full w-full max-w-md border-l border-neutral-200 flex flex-col rounded-l-[12px] animate-slide-up overflow-hidden">
            <div className="p-5 border-b border-neutral-200 bg-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-1 h-3 bg-accent-500"></div>
                <h3 className="text-[11px] font-bold text-primary-900 uppercase tracking-widest">{t("ws.evidence.title")}</h3>
              </div>
              <Button variant="ghost" size="sm" className="text-neutral-500 hover:text-primary-900 text-[10px] font-bold tracking-widest uppercase" onClick={() => setActiveEvidence(null)}>{t("ws.evidence.close")}</Button>
            </div>
            <div className="p-6 overflow-y-auto space-y-8 flex-1">
              <div>
                <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{t("ws.evidence.claim")}</p>
                <p className="text-[15px] font-medium text-primary-900 leading-relaxed">{activeEvidence.claim}</p>
              </div>
              <div className="pl-4 border-l-2 border-accent-500/30">
                <p className="text-[10px] font-bold text-accent-600 uppercase tracking-widest mb-1">{t("ws.evidence.exact")}</p>
                <p className="text-[14px] text-neutral-700 italic leading-relaxed font-medium">"{activeEvidence.evidence}"</p>
              </div>
              <div>
                <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">{t("ws.evidence.reference")}</p>
                <div className="inline-flex items-center gap-2 bg-white border border-neutral-200 px-3 py-1.5 rounded-[4px] text-[12px] font-bold text-primary-900 shadow-sm">
                  <FileText className="w-3.5 h-3.5 text-accent-500" />
                  {activeEvidence.source}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="h-12 bg-white border-b border-neutral-200 flex items-center px-6 shrink-0 justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="text-[10px] font-bold text-neutral-400 hover:text-primary-900 uppercase tracking-widest transition-colors flex items-center gap-1">
            {t("ws.back")}
          </button>
          <div className="w-px h-3 bg-neutral-200 hidden sm:block"></div>
          <div className="flex items-center gap-2 text-[11px] font-bold text-primary-900 uppercase tracking-widest">
            <span className="text-neutral-400 font-normal">{t("ws.document")}</span>
            <span className="truncate max-w-[200px] sm:max-w-xs">{document.filename}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-primary-900 bg-neutral-100 border border-neutral-200 px-2.5 py-0.5 rounded">
          {language}
        </div>
      </header>

      {/* Workspace Area */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden w-full relative">
        
        {/* Left Panel - Document Intelligence */}
        <div className="w-full md:w-[45%] lg:w-[40%] border-r border-neutral-200 bg-neutral-50 bg-grid-pattern-subtle overflow-y-auto hide-scrollbar flex flex-col z-10 relative">
          
          {/* Shimmer Overlay during translation */}
          <div className={`absolute inset-0 z-20 pointer-events-none transition-opacity duration-500 bg-gradient-to-b from-white/0 via-white/50 to-white/0 ${isTranslating ? 'opacity-100' : 'opacity-0'}`}>
            <div className="absolute inset-0 bg-[linear-gradient(110deg,transparent_20%,rgba(255,255,255,0.7)_50%,transparent_80%)] bg-[length:200%_100%] animate-shimmer" style={{ animation: 'shimmer 2s infinite linear' }}></div>
          </div>

          <div className={`p-6 md:p-8 space-y-12 transition-all duration-500 ${isTranslating ? 'opacity-50 blur-[1px]' : 'opacity-100 blur-0'}`}>
            
            {/* Document Story */}
            <div className="space-y-3" key={`story-${language}`}>
              <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2 transition-all duration-300 animate-slide-up">
                <span className="w-1 h-2.5 bg-primary-900"></span>{t("ws.document_story")}
              </h2>
              {intel ? (
                <p className="text-[15px] text-primary-900 font-medium leading-relaxed transition-all duration-300 animate-slide-up">
                  {intel.document_story || intel.simple_summary}
                </p>
              ) : (
                <p className="text-[13px] text-neutral-500 font-medium">{t("ws.processing_incomplete")}</p>
              )}
            </div>

            {/* WHAT CHANGED? */}
            {intel?.changes && intel.changes.length > 0 && (
              <div className="space-y-4" key={`changes-${language}`}>
                <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2 transition-all duration-300 animate-slide-up">
                  <span className="w-1 h-2.5 bg-primary-900"></span>{t("ws.what_changed")}
                </h2>
                <div className="flex flex-col gap-3">
                  {intel.changes.map((change, idx) => (
                    <div key={idx} className="bg-white border border-neutral-200 rounded-[6px] p-4 hover:border-accent-500/30 transition-all duration-300 animate-slide-up shadow-sm gap-2" style={{ animationDelay: `${idx * 50}ms` }}>
                      <div className="flex justify-between items-start mb-2">
                         <span className="text-[13px] font-bold text-primary-900">{change.metric}</span>
                         <span className={`text-[13px] font-bold ${change.change.startsWith('+') ? 'text-success-600' : change.change.startsWith('-') ? 'text-error-600' : 'text-primary-900'}`}>{change.change}</span>
                      </div>
                      {(change.previous_value || change.current_value) && (
                        <div className="flex items-center gap-2 text-[11px] text-neutral-500 mb-2 font-medium">
                          <span>{change.previous_value || 'N/A'}</span>
                          <ArrowRight className="w-3 h-3" />
                          <span>{change.current_value || 'N/A'}</span>
                        </div>
                      )}
                      <p className="text-[12px] text-neutral-600 font-medium leading-relaxed">{change.explanation}</p>
                      
                      <div className="mt-3 flex justify-end">
                         <Button variant="ghost" size="sm" className="h-6 text-[10px] px-2 text-accent-600 hover:bg-accent-50 transition-colors" onClick={() => setActiveEvidence({ claim: `Change in ${change.metric}`, evidence: `Context provided in document regarding ${change.metric}.`, source: change.evidence_reference })}>
                            <FileSearch className="w-3 h-3 mr-1" />
                            {t("ws.verify")}
                         </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* WHAT CONNECTS? */}
            {intel?.relationships && intel.relationships.length > 0 && (
              <div className="space-y-4" key={`connects-${language}`}>
                 <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2 transition-all duration-300 animate-slide-up">
                  <span className="w-1 h-2.5 bg-primary-900"></span>{t("ws.what_connects")}
                 </h2>
                 <div className="flex flex-col gap-3">
                   {intel.relationships.map((rel, idx) => (
                      <div key={idx} className="bg-white border border-neutral-200 rounded-[6px] p-4 shadow-sm animate-slide-up" style={{ animationDelay: `${idx * 50}ms` }}>
                         <p className="text-[14px] font-bold text-primary-900 leading-snug mb-2">{rel.observation}</p>
                         <p className="text-[13px] text-neutral-600 mb-3 leading-relaxed">{rel.why_it_may_matter}</p>
                         
                         {rel.uncertainty && (
                            <div className="bg-warning-50 p-2.5 rounded-[4px] text-[11.5px] text-warning-700 font-medium mb-3 border border-warning-100">
                               {rel.uncertainty}
                            </div>
                         )}
                         <Button variant="outline" size="sm" className="h-7 text-[10px] w-full mt-1 border-neutral-200 hover:border-accent-500 hover:text-accent-600 transition-colors" onClick={() => handleAsk(`Explore the connection: ${rel.observation}`)}>
                            {t("ws.explore")} <ArrowRight className="w-3 h-3 ml-1" />
                         </Button>
                      </div>
                   ))}
                 </div>
              </div>
            )}

            {/* AREAS WORTH UNDERSTANDING */}
            {intel?.areas_to_understand && intel.areas_to_understand.length > 0 && (
              <div className="space-y-4" key={`areas-${language}`}>
                 <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2 transition-all duration-300 animate-slide-up">
                  <span className="w-1 h-2.5 bg-primary-900"></span>{t("ws.areas_to_understand")}
                 </h2>
                 <div className="flex flex-col gap-3">
                    {intel.areas_to_understand.map((area, idx) => (
                        <div key={idx} className="bg-white border border-neutral-200 rounded-[6px] p-4 shadow-sm animate-slide-up border-l-[3px] border-l-primary-900" style={{ animationDelay: `${idx * 50}ms` }}>
                            <p className="text-[11px] font-extrabold text-primary-900 uppercase tracking-widest mb-1.5">{area.title}</p>
                            <p className="text-[13px] text-neutral-600 mb-3 leading-relaxed">{area.description}</p>
                            <Button variant="outline" size="sm" className="h-7 text-[10px] border-neutral-200 hover:border-primary-900 hover:text-primary-900 transition-colors" onClick={() => handleAsk(`Explore ${area.title}: ${area.description}`)}>
                              {t("ws.explore")} <ArrowRight className="w-3 h-3 ml-1" />
                            </Button>
                        </div>
                    ))}
                 </div>
              </div>
            )}

            {/* YOUR INVESTIGATION */}
            {intel?.investigation_paths && intel.investigation_paths.length > 0 && (
               <div className="space-y-4" key={`investigation-${language}`}>
                  <h2 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2 transition-all duration-300 animate-slide-up">
                    <span className="w-1 h-2.5 bg-primary-900"></span>{t("ws.your_investigation")}
                  </h2>
                  <div className="bg-white border border-neutral-200 rounded-[6px] shadow-sm overflow-hidden animate-slide-up">
                     {intel.investigation_paths.map((path, idx) => (
                        <button key={idx} onClick={() => handleAsk(path.question)} className={`w-full text-left p-4 flex items-center justify-between hover:bg-neutral-50 transition-colors group ${idx < intel.investigation_paths.length - 1 ? 'border-b border-neutral-100' : ''}`}>
                            <div className="flex items-center gap-3">
                               <div className="w-6 h-6 rounded-full bg-neutral-100 text-neutral-500 flex items-center justify-center text-[11px] font-bold shrink-0 group-hover:bg-accent-50 group-hover:text-accent-600 transition-colors">{idx + 1}</div>
                               <span className="text-[13px] font-medium text-primary-900 group-hover:text-accent-600 transition-colors pr-4">{path.question}</span>
                            </div>
                            <ArrowRight className="w-4 h-4 text-neutral-300 group-hover:text-accent-500 transition-colors shrink-0" />
                        </button>
                     ))}
                  </div>
               </div>
            )}


            {/* Impact Lens */}
            {intel?.financial_terms && intel.financial_terms.length > 0 && (
              <div className="space-y-8 pb-12 relative before:absolute before:-inset-6 before:bg-grid-pattern before:opacity-30 before:-z-10 before:pointer-events-none">
                <div className="flex items-center gap-2 border-b border-neutral-200 pb-3">
                  <h2 className="text-[12px] font-bold text-primary-900 uppercase tracking-widest">{t("ws.impact_lens")}</h2>
                  <span className="text-[11px] font-medium text-neutral-500 ml-2">{t("ws.impact_lens.sub")}</span>
                </div>
                
                {intel.financial_terms.map((term, idx) => (
                  <div key={idx} className="space-y-5 pt-1">
                    <p className="font-extrabold text-[20px] text-primary-900 font-heading tracking-tight">{term.term}</p>
                    
                    {/* Visual Reasoning Path (matches Intelligence Path) */}
                    <div className="pl-5 border-l-2 border-neutral-200 space-y-6 ml-2 relative">
                      
                      <div className="relative">
                        <div className="absolute -left-[27px] top-1.5 w-2.5 h-2.5 bg-neutral-100 border-2 border-neutral-300 rounded-full"></div>
                        <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{t("ws.concept")}</p>
                        <p className="text-[14px] text-primary-900 font-medium leading-relaxed">{term.plain_language_definition}</p>
                      </div>
                      
                      <div className="relative">
                        <div className="absolute -left-[27px] top-1.5 w-2.5 h-2.5 bg-neutral-100 border-2 border-neutral-300 rounded-full"></div>
                        <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{t("ws.why_matters")}</p>
                        <p className="text-[14px] text-neutral-700 font-medium leading-relaxed">{term.why_it_matters_general}</p>
                      </div>

                      <div className="relative">
                        <div className="absolute -left-[27px] top-1.5 w-2.5 h-2.5 bg-neutral-100 border-2 border-neutral-300 rounded-full"></div>
                        <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">{t("ws.questions")}</p>
                        <div className="space-y-2">
                          <button 
                            className="flex items-center gap-2 text-[12px] font-bold text-accent-600 hover:text-accent-700 transition-colors"
                            onClick={() => handleAsk(`How does ${term.term} affect the overall health of the business?`)}
                          >
                            <CornerDownRight className="w-3.5 h-3.5 opacity-70" />
                            {t("ws.questions.health")}
                          </button>
                          <button 
                            className="flex items-center gap-2 text-[12px] font-bold text-accent-600 hover:text-accent-700 transition-colors"
                            onClick={() => handleAsk(`What usually causes ${term.term} to change?`)}
                          >
                            <CornerDownRight className="w-3.5 h-3.5 opacity-70" />
                            {t("ws.questions.causes")}
                          </button>
                        </div>
                      </div>

                      <div className="relative pt-2">
                        <div className="absolute -left-[27px] top-3.5 w-2.5 h-2.5 bg-white border-2 border-accent-500 rounded-full"></div>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="text-[10px] text-primary-900 font-bold uppercase tracking-widest border-neutral-300 bg-white hover:border-accent-500 hover:text-accent-600 transition-colors rounded-[4px] shadow-sm" 
                          onClick={() => setActiveEvidence({ claim: `Definition of ${term.term}`, evidence: `Context provided in document regarding ${term.term}.`, source: term.evidence_reference })}
                        >
                          <FileSearch className="w-3 h-3 mr-1.5 text-accent-500" />
                          {t("ws.verify")}
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - ASK BHARAT */}
        <div className="w-full md:w-[55%] lg:w-[60%] bg-white bg-grid-pattern-subtle flex flex-col h-full relative">
          
          <div className="px-6 md:px-10 py-3 border-b border-neutral-100 flex items-center justify-between shrink-0 bg-neutral-50/50">
            <h2 className="text-[11px] font-bold text-primary-900 uppercase tracking-widest flex items-center gap-2">
               {t("home.ask_bharat")}
            </h2>
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{t("ws.ai_educator")}</span>
          </div>

          <div className="flex-1 overflow-y-auto hide-scrollbar px-6 md:px-10 py-8 space-y-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-start justify-center max-w-lg mt-4 animate-fade-in">
                <h3 className="text-[24px] font-extrabold text-primary-900 font-heading tracking-tight leading-snug">
                  {t("qa.greeting")}
                </h3>
                
                <div className="w-full space-y-2 mt-6">
                  {[
                    t("qa.q1"),
                    t("qa.q2"),
                    t("qa.q3")
                  ].map((q, i) => (
                    <button key={i} onClick={() => handleAsk(q)} className="flex items-center justify-between py-2.5 px-4 w-full text-left border border-neutral-200 rounded-[6px] hover:border-accent-500 group transition-all shadow-sm">
                      <span className="text-[13px] font-bold text-primary-900 group-hover:text-accent-600 transition-colors">{q}</span>
                      <ArrowRight className="w-4 h-4 text-neutral-300 group-hover:text-accent-500 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Chat Messages */}
            <div className="space-y-10 pb-4">
              {messages.map((msg) => (
                <div key={msg.id} className="flex flex-col animate-slide-up">
                  {msg.role === 'user' ? (
                    <div className="flex gap-4 items-start self-end max-w-[85%]">
                      <div className="bg-neutral-100 border border-neutral-200 rounded-[8px] rounded-tr-none p-3 shadow-sm">
                        <p className="text-[14px] font-medium text-primary-900 leading-relaxed">{msg.content}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-4 max-w-[90%]">
                      {/* Editorial Intelligence format */}
                      <div className="space-y-4">
                        <div className="flex items-center gap-2">
                          <span className="w-1 h-3 bg-accent-500 block"></span>
                          <span className="text-[10px] font-bold text-accent-600 uppercase tracking-widest">{t("home.bharat_explains")}</span>
                        </div>
                        
                        <div className="text-[14px] text-primary-900 leading-relaxed font-medium whitespace-pre-wrap">
                          {msg.content}
                        </div>

                        {msg.responseMeta && (msg.responseMeta.evidence_snippet || msg.responseMeta.source_reference) && (
                          <div className="mt-4 pt-3 border-t border-neutral-100 flex flex-col items-start gap-2">
                            <button 
                              className="flex items-center gap-1.5 text-[9px] font-bold text-primary-900 bg-neutral-50 border border-neutral-200 px-2.5 py-1 rounded-[4px] uppercase tracking-widest hover:bg-neutral-100 transition-colors shadow-sm"
                              onClick={() => setActiveEvidence({
                                claim: t("ws.evidence.ai_explanation"),
                                evidence: msg.responseMeta?.evidence_snippet || t("ws.evidence.snippet_available"),
                                source: msg.responseMeta?.source_reference || t("ws.document")
                              })}
                            >
                              {t("ws.evidence.source")} · {msg.responseMeta?.source_reference || 'Document'}
                              <FileSearch className="w-3 h-3 ml-1 text-accent-500" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {isLoading && (
                <div className="flex flex-col gap-4 max-w-[90%] animate-pulse">
                   <div className="flex items-center gap-2">
                      <span className="w-1 h-2.5 bg-neutral-300 block"></span>
                      <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{t("ws.processing")}</span>
                    </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Assistant Input */}
          <div className="p-4 md:p-6 bg-white border-t border-neutral-200 z-20 shrink-0">
            <div className="relative flex items-center bg-white border border-neutral-300 rounded-[6px] focus-within:border-accent-500 transition-all shadow-sm">
              <input 
                type="text" 
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder={t("ws.placeholder")} 
                className="w-full pl-4 pr-24 py-3 bg-transparent outline-none text-[14px] text-primary-900 font-medium placeholder-neutral-400"
                disabled={isLoading}
              />
              <div className="absolute right-1.5 top-1.5 bottom-1.5 flex items-center gap-1">
                {recognitionRef.current && (
                  <button 
                    onClick={toggleRecording} 
                    disabled={isLoading}
                    className={`flex items-center justify-center w-8 h-8 rounded-[4px] transition-colors ${
                      isRecording 
                        ? 'text-white bg-error-600 shadow-[0_0_0_4px_rgba(220,38,38,0.2)] animate-pulse' 
                        : 'text-neutral-500 hover:text-primary-900 hover:bg-neutral-100'
                    }`}
                  >
                    <Mic className="h-4 w-4" />
                  </button>
                )}
                <button 
                  onClick={() => handleAsk()} 
                  disabled={!inputValue.trim() || isLoading}
                  className="flex items-center justify-center w-8 h-8 rounded-[4px] text-white bg-primary-900 hover:bg-primary-800 disabled:opacity-50 disabled:bg-neutral-300 transition-colors"
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
