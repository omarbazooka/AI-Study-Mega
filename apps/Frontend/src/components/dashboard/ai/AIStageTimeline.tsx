import React from "react";
import { getStageMessage } from "./pipeline-stage-messages";

interface AIStageTimelineProps {
  currentStage: string | null;
  completedStages: string[];
  metadata?: Record<string, any>;
}

interface TimelineItem {
  id: string;
  label: string;
  stages: string[];
}

const TIMELINE_ITEMS: TimelineItem[] = [
  {
    id: "understanding",
    label: "Understanding request",
    stages: ["request_received", "document_check", "input_analysis", "planning"]
  },
  {
    id: "searching",
    label: "Searching document",
    stages: ["personalization", "query_preparation", "retrieval", "reranking", "context_building"]
  },
  {
    id: "generating",
    label: "Generating response",
    stages: ["generation", "quiz_generation", "refining"]
  },
  {
    id: "verifying",
    label: "Verifying grounding",
    stages: ["verification", "citations", "finalizing"]
  }
];

export const AIStageTimeline: React.FC<AIStageTimelineProps> = ({
  currentStage,
  completedStages,
  metadata,
}) => {
  const activeStageLower = currentStage?.toLowerCase() || "";

  // Check if personalization is active or completed, or not applied
  const isPersonalizationApplied = metadata?.personalization_applied || completedStages.includes("personalization") || activeStageLower === "personalization";

  return (
    <div className="flex flex-col gap-3.5 pl-2 select-none border-l border-zinc-800/80 ml-6 py-1">
      {TIMELINE_ITEMS.map((item) => {
        // If searching group, and personalization is not applied, we skip checking it in our calculations
        const groupStages = item.id === "searching" && !isPersonalizationApplied
          ? item.stages.filter(s => s !== "personalization")
          : item.stages;

        const isGroupActive = groupStages.includes(activeStageLower);
        const isGroupCompleted = groupStages.every((s) => completedStages.includes(s)) && !isGroupActive;
        const isGroupUpcoming = !isGroupActive && !isGroupCompleted;

        // Opacities:
        // - Completed: 35-40% opacity
        // - Active Title: 70-75%, Active Description: 40-48%
        // - Upcoming: 20-28%
        let titleOpacity = "opacity-25";
        let descOpacity = "opacity-0 h-0 overflow-hidden";
        let dotColor = "bg-zinc-800 border-zinc-700";

        if (isGroupCompleted) {
          titleOpacity = "opacity-35 font-medium";
          dotColor = "bg-purple-500/30 border-purple-500/50";
        } else if (isGroupActive) {
          titleOpacity = "opacity-75 font-semibold text-purple-400";
          descOpacity = "opacity-45 mt-0.5 text-xs text-zinc-300 transition-all duration-300";
          dotColor = "bg-purple-500 border-purple-400 shadow-[0_0_8px_rgba(168,85,247,0.5)]";
        } else if (isGroupUpcoming) {
          titleOpacity = "opacity-20 font-normal";
        }

        // Get descriptive message for active stage in the group
        let description = "";
        if (isGroupActive) {
          const msg = getStageMessage(activeStageLower, metadata);
          description = msg.description;
        }

        return (
          <div key={item.id} className="relative flex gap-3 items-start">
            {/* Timeline Dot */}
            <div
              className={`w-2.5 h-2.5 rounded-full border z-10 -ml-[13.5px] mt-1.5 transition-all duration-500 ${dotColor}`}
            />

            {/* Stage Title and Description */}
            <div className="flex flex-col">
              <span className={`text-xs tracking-wide transition-opacity duration-500 ${titleOpacity}`}>
                {item.label}
              </span>
              {description && (
                <span className={descOpacity}>
                  {description}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
