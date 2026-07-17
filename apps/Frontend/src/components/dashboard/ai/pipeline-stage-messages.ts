export interface StageMessage {
  title: string;
  description: string;
}

export const PIPELINE_STAGE_MESSAGES: Record<string, StageMessage> = {
  request_received: {
    title: "Request received",
    description: "Establishing secure connection to the AI study service."
  },
  document_check: {
    title: "Checking document status",
    description: "Validating user permissions and document availability."
  },
  input_analysis: {
    title: "Analyzing input query",
    description: "Parsing query structure and extracting key concepts."
  },
  planning: {
    title: "Planning task execution",
    description: "Creating the optimal execution plan for your request."
  },
  personalization: {
    title: "Applying personalization",
    description: "Injecting your language and learning preferences."
  },
  query_preparation: {
    title: "Preparing search terms",
    description: "Formulating key search terms and academic keywords."
  },
  retrieval: {
    title: "Searching the document",
    description: "Querying vector database index for matching excerpts."
  },
  reranking: {
    title: "Selecting relevant sources",
    description: "Scoring and filtering retrieved text segments for high relevance."
  },
  context_building: {
    title: "Structuring evidence",
    description: "Assembling selected document context into a cohesive format."
  },
  generation: {
    title: "Writing the response",
    description: "Synthesizing answer grounded strictly in retrieved facts."
  },
  quiz_generation: {
    title: "Creating quiz questions",
    description: "Drafting questions directly from the verified source text."
  },
  verification: {
    title: "Checking accuracy",
    description: "Validating answers against document truth to ensure no hallucinations."
  },
  refining: {
    title: "Refining the response",
    description: "Improving output text using verification feedback loop."
  },
  citations: {
    title: "Connecting source references",
    description: "Linking assertions to their corresponding page numbers and sections."
  },
  finalizing: {
    title: "Finalizing response",
    description: "Formatting and preparing verified answer for display."
  },
  completed: {
    title: "Response ready",
    description: "Successfully processed and verified."
  },
  failed: {
    title: "Process failed",
    description: "An unexpected error occurred during processing."
  },
  cancelled: {
    title: "Process cancelled",
    description: "Request aborted by user."
  }
};

export function getStageMessage(stage: string, metadata?: Record<string, any>): StageMessage {
  const base = PIPELINE_STAGE_MESSAGES[stage] || {
    title: stage.charAt(0).toUpperCase() + stage.slice(1).replace(/_/g, " "),
    description: "Processing..."
  };

  // Dynamically enrich descriptions if metadata is available
  if (metadata) {
    if (stage === "retrieval" && typeof metadata.candidate_count === "number") {
      return {
        ...base,
        description: `Found ${metadata.candidate_count} sections matching query.`
      };
    }
    if (stage === "reranking" && typeof metadata.selected_source_count === "number") {
      return {
        ...base,
        description: `Selected ${metadata.selected_source_count} relevant sources.`
      };
    }
    if (stage === "citations" && typeof metadata.cited_source_count === "number") {
      return {
        ...base,
        description: `Linked response to ${metadata.cited_source_count} precise sections.`
      };
    }
    if (stage === "refining" && typeof metadata.retry_count === "number") {
      return {
        ...base,
        description: `Correcting response quality (attempt ${metadata.retry_count}).`
      };
    }
  }

  return base;
}
