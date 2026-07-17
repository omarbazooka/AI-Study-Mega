import React from "react";
import { AIProcessingOrb } from "./AIProcessingOrb";
import { AIStageTimeline } from "./AIStageTimeline";
import { WordRevealText } from "./WordRevealText";
import { getStageMessage } from "./pipeline-stage-messages";

interface AIProcessingIndicatorProps {
  stage: string | null;
  progress: number;
  status: string | null; // "started", "progress", "completed", "failed", "cancelled"
  completedStages: string[];
  publicRequestSummary?: string | null;
  metadata?: Record<string, any>;
}

export const AIProcessingIndicator: React.FC<AIProcessingIndicatorProps> = ({
  stage,
  progress,
  status,
  completedStages,
  publicRequestSummary,
  metadata,
}) => {
  if (!stage || status === "completed") return null;

  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";
  const activeStageLower = stage.toLowerCase();
  const currentMsg = getStageMessage(activeStageLower, metadata);

  return (
    <div className="w-full max-w-xl rounded-2xl border border-zinc-800/80 bg-[#161616]/30 backdrop-blur-md p-4 flex flex-col gap-4 shadow-xl select-none">
      {/* Top Header Row: Orb & Active Title */}
      <div className="flex items-center gap-3.5">
        <AIProcessingOrb status={status} />

        <div className="flex flex-col">
          <WordRevealText
            key={activeStageLower} // Re-mount when active stage changes to restart reveal
            text={currentMsg.title}
            speed={40}
            className={`text-sm font-semibold tracking-wide transition-colors duration-500 ${
              isFailed ? "text-red-400" : isCancelled ? "text-zinc-400" : "text-purple-400/90"
            }`}
          />
          <span className="text-2xs text-zinc-500 tracking-wider font-semibold uppercase mt-0.5">
            {isFailed ? "Error" : isCancelled ? "Cancelled" : `Processing (${Math.round(progress)}%)`}
          </span>
        </div>
      </div>

      {/* Public Request Summary */}
      {publicRequestSummary && !isFailed && !isCancelled && (
        <div className="px-1 text-xs text-zinc-400/85 leading-relaxed italic border-l-2 border-purple-500/30 pl-3 py-0.5 opacity-40">
          &ldquo;{publicRequestSummary}&rdquo;
        </div>
      )}

      {/* Vertical Timeline */}
      {!isFailed && !isCancelled && (
        <AIStageTimeline
          currentStage={stage}
          completedStages={completedStages}
          metadata={metadata}
        />
      )}

      {/* Error Message for Failures */}
      {isFailed && (
        <div className="text-xs text-red-400/90 bg-red-950/20 border border-red-900/30 rounded-xl p-3 leading-relaxed">
          The processing pipeline encountered an issue: {metadata?.error_message || "Operation failed."}
        </div>
      )}

      {/* Cancelled Message */}
      {isCancelled && (
        <div className="text-xs text-zinc-400/90 bg-zinc-950/20 border border-zinc-900/30 rounded-xl p-3 leading-relaxed">
          The processing operation was cancelled by the client.
        </div>
      )}

      {/* Premium Progress Bar */}
      <div className="w-full h-1.5 rounded-full bg-zinc-950/80 overflow-hidden relative border border-zinc-900/50">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            isFailed
              ? "bg-red-500"
              : isCancelled
              ? "bg-zinc-600"
              : "bg-gradient-to-r from-purple-600 via-purple-500 to-indigo-500 shadow-[0_0_8px_rgba(168,85,247,0.3)]"
          }`}
          style={{ width: `${Math.max(2, Math.min(100, progress))}%` }}
        />
      </div>
    </div>
  );
};
