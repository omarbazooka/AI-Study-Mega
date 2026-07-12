/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/set-state-in-effect, @typescript-eslint/no-unused-vars */
import { useState, useEffect, useRef, useCallback } from "react";
import { documentsService } from "@/services/documents.service";
import { DocumentStatus, StatusResponse } from "@/types/api/documents";

interface UseDocumentStatusOptions {
  onStatusChanged?: (status: DocumentStatus, details: StatusResponse) => void;
  onReady?: () => void;
  onFailed?: (errorMessage?: string | null) => void;
}

export function useDocumentStatus(
  documentId: string | null,
  initialStatus?: DocumentStatus | null,
  isDocsLoading?: boolean,
  options?: UseDocumentStatusOptions
) {
  const [status, setStatus] = useState<DocumentStatus | null>(initialStatus || null);
  const [details, setDetails] = useState<StatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activePollDocId = useRef<string | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  // Sync state when initialStatus changes
  useEffect(() => {
    if (initialStatus) {
      setStatus(initialStatus);
    }
  }, [initialStatus]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
    activePollDocId.current = null;
  }, []);

  const startPolling = useCallback((docId: string) => {
    stopPolling();
    setIsPolling(true);
    activePollDocId.current = docId;

    let attempts = 0;
    const maxAttempts = 50;

    const poll = async () => {
      if (activePollDocId.current !== docId) return;

      try {
        const response = await documentsService.getDocumentStatus(docId);
        if (activePollDocId.current !== docId) return;

        setStatus(response.status);
        setDetails(response);

        if (optionsRef.current?.onStatusChanged) {
          optionsRef.current.onStatusChanged(response.status, response);
        }

        // Terminal state checks
        if (response.status === "ready") {
          stopPolling();
          if (optionsRef.current?.onReady) optionsRef.current.onReady();
          return;
        }

        if (response.status === "failed") {
          stopPolling();
          if (optionsRef.current?.onFailed) optionsRef.current.onFailed(response.error_message);
          return;
        }

        attempts++;
        if (attempts >= maxAttempts) {
          stopPolling();
          setStatus("failed");
          if (optionsRef.current?.onFailed) optionsRef.current.onFailed("Polling timed out.");
          return;
        }

        // Poll again after 2 seconds
        pollTimerRef.current = setTimeout(poll, 2000);
      } catch (err) {
        // Stop polling on HTTP error
        stopPolling();
        setStatus("failed");
        if (optionsRef.current?.onFailed) optionsRef.current.onFailed("Failed to fetch document status.");
      }
    };

    poll();
  }, [stopPolling]);

  useEffect(() => {
    if (documentId && !isDocsLoading) {
      const currentStatus = status || initialStatus;
      if (currentStatus !== "ready" && currentStatus !== "failed") {
        startPolling(documentId);
      }
    } else if (!documentId && !isDocsLoading) {
      setStatus(null);
      setDetails(null);
      stopPolling();
    }

    return () => {
      stopPolling();
    };
    // Only re-run when documentId or loading status changes to prevent loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, isDocsLoading]);

  const reprocess = async () => {
    if (!documentId) return;
    setIsReprocessing(true);
    setStatus("stored");
    try {
      await documentsService.reprocessDocument(documentId);
      setIsReprocessing(false);
      startPolling(documentId);
    } catch (err) {
      setIsReprocessing(false);
      setStatus("failed");
      if (options?.onFailed) options.onFailed("Reprocessing failed to initialize.");
    }
  };

  return {
    status,
    details,
    isPolling,
    isReprocessing,
    reprocess,
    forceRefresh: () => documentId && startPolling(documentId),
  };
}
