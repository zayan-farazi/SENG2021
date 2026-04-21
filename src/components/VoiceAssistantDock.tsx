import { Mic, MicOff, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AssistantActionResult, AssistantContext } from "../voiceAssistant";
import "./voice-assistant.css";

type BrowserSpeechRecognition = SpeechRecognition;

type VoiceAssistantDockProps = {
  context: AssistantContext;
  hint: string;
  disabledReason?: string | null;
  liveTranscript?: string | null;
  streaming?: boolean;
  onPartialTranscript?: (transcript: string) => void;
  onTranscript: (transcript: string) => Promise<AssistantActionResult>;
};

type VoiceAssistantLogEntry = {
  tone: "heard" | "success" | "warning";
  text: string;
};

type PendingAssistantConfirmation = {
  message: string;
  confirmLabel: string;
  execute: () => Promise<AssistantActionResult>;
};

export function VoiceAssistantDock({
  context,
  hint,
  disabledReason = null,
  liveTranscript = null,
  streaming = false,
  onPartialTranscript,
  onTranscript,
}: VoiceAssistantDockProps) {
  const [speechSupported, setSpeechSupported] = useState(true);
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<VoiceAssistantLogEntry[]>([]);
  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingAssistantConfirmation | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const transcriptHandlerRef = useRef(onTranscript);
  const partialTranscriptHandlerRef = useRef(onPartialTranscript);

  useEffect(() => {
    transcriptHandlerRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    partialTranscriptHandlerRef.current = onPartialTranscript;
  }, [onPartialTranscript]);

  const appendLog = (tone: VoiceAssistantLogEntry["tone"], text: string) => {
    setLog(current => [...current.slice(-5), { tone, text }]);
  };

  const applyResult = (result: AssistantActionResult) => {
    if (result.kind === "confirm") {
      setPendingConfirmation({
        message: result.message,
        confirmLabel: result.confirmLabel ?? "Confirm",
        execute: result.execute,
      });
      appendLog("warning", result.message);
      return;
    }

    appendLog(result.kind === "applied" ? "success" : "warning", result.message);
  };

  const handleTranscript = async (transcript: string) => {
    const cleaned = transcript.trim();
    if (!cleaned) {
      return;
    }

    appendLog("heard", `Heard: ${cleaned}`);
    setBusy(true);
    setPendingConfirmation(null);

    try {
      const result = await transcriptHandlerRef.current(cleaned);
      applyResult(result);
    } catch {
      appendLog("warning", "The assistant could not apply that command.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (disabledReason) {
      setListening(false);
      return;
    }

    const SpeechRecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setSpeechSupported(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = streaming;
    recognition.interimResults = streaming;
    recognition.lang = "en-AU";
    recognition.onstart = () => {
      setListening(true);
    };
    recognition.onresult = event => {
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result) {
          continue;
        }
        const alternative = result[0];
        const transcript =
          typeof alternative?.transcript === "string" ? alternative.transcript.trim() : "";
        if (!transcript) {
          continue;
        }

        if (result.isFinal) {
          void handleTranscript(transcript);
        } else {
          interimTranscript = transcript;
        }
      }

      if (interimTranscript && partialTranscriptHandlerRef.current) {
        partialTranscriptHandlerRef.current(interimTranscript);
      }
    };
    recognition.onerror = event => {
      setListening(false);
      const errorLabel = "error" in event && typeof event.error === "string" ? event.error : "unknown";
      appendLog("warning", `Speech recognition error: ${errorLabel}.`);
    };
    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
    return () => {
      recognition.stop();
      recognitionRef.current = null;
    };
  }, [disabledReason, streaming]);

  const startListening = () => {
    if (!recognitionRef.current || disabledReason || busy) {
      return;
    }

    recognitionRef.current.start();
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  const confirmPendingAction = async () => {
    if (!pendingConfirmation) {
      return;
    }

    setBusy(true);
    const action = pendingConfirmation;
    setPendingConfirmation(null);

    try {
      const result = await action.execute();
      applyResult(result);
    } catch {
      appendLog("warning", "The assistant could not complete that confirmed action.");
    } finally {
      setBusy(false);
    }
  };

  const isDisabled = !speechSupported || Boolean(disabledReason);
  const contextLabel =
    context === "marketplace"
      ? "Marketplace assistant"
      : context === "checkout"
        ? "Checkout assistant"
        : "Documents assistant";

  return (
    <section className="voice-assistant-dock" aria-label={`${contextLabel} voice controls`}>
      <div className="voice-assistant-header">
        <div>
          <p className="voice-assistant-eyebrow">{contextLabel}</p>
          <h2>Voice assistant</h2>
        </div>
        <div className="voice-assistant-actions">
          <button
            type="button"
            className="voice-assistant-button voice-assistant-button-primary"
            onClick={startListening}
            disabled={isDisabled || listening || busy}
          >
            <Mic size={16} strokeWidth={2.2} />
            Start
          </button>
          <button
            type="button"
            className="voice-assistant-button"
            onClick={stopListening}
            disabled={!listening}
          >
            <MicOff size={16} strokeWidth={2.2} />
            Stop
          </button>
        </div>
      </div>

      <p className="voice-assistant-hint">
        <Sparkles size={14} strokeWidth={2.2} />
        <span>{disabledReason ?? hint}</span>
      </p>

      {liveTranscript ? (
        <p className="voice-assistant-live" aria-live="polite">
          Listening: {liveTranscript}
        </p>
      ) : null}

      {pendingConfirmation ? (
        <div className="voice-assistant-confirmation" role="alert">
          <strong>{pendingConfirmation.message}</strong>
          <div className="voice-assistant-confirmation-actions">
            <button
              type="button"
              className="voice-assistant-button voice-assistant-button-primary"
              onClick={() => {
                void confirmPendingAction();
              }}
              disabled={busy}
            >
              {pendingConfirmation.confirmLabel}
            </button>
            <button
              type="button"
              className="voice-assistant-button"
              onClick={() => {
                setPendingConfirmation(null);
                appendLog("warning", "Voice action cancelled.");
              }}
              disabled={busy}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <div className="voice-assistant-log" aria-live="polite">
        {log.length === 0 ? (
          <p className="voice-assistant-empty">No voice actions yet.</p>
        ) : (
          log.map((entry, index) => (
            <p key={`${entry.tone}-${index}`} className={`voice-assistant-log-entry voice-assistant-log-${entry.tone}`}>
              {entry.text}
            </p>
          ))
        )}
      </div>
    </section>
  );
}
