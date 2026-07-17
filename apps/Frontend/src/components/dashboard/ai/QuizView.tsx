/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
import React, { useState } from "react";
import { aiService } from "@/services/ai.service";
import { quizService } from "@/services/quiz.service";
import { AIResponse } from "@/types/api/ai";
import { QuizDetail, QuizSubmissionResponse, QuizResponseItem } from "@/types/api/quiz";
import { QuizResult } from "./QuizResult";
import { Award, Loader2, Sparkles, AlertCircle, CheckCircle2 } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { toast } from "sonner";

interface QuizViewProps {
  documentId: string | null;
  sessionId: string | null;
  disabled: boolean;
}

export const QuizView: React.FC<QuizViewProps> = ({
  documentId,
  sessionId,
  disabled,
}) => {
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [numQuestions, setNumQuestions] = useState<number>(5);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [quizDetail, setQuizDetail] = useState<QuizDetail | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizResult, setQuizResult] = useState<QuizSubmissionResponse | null>(null);

  const handleGenerateQuiz = async () => {
    if (!documentId || !sessionId || isLoading || disabled) return;

    setIsLoading(true);
    setQuizDetail(null);
    setQuizResult(null);
    setSelectedAnswers({});
    
    try {
      const response: AIResponse = await aiService.generateQuiz(documentId, {
        session_id: sessionId,
        difficulty,
        number_of_questions: numQuestions,
        question_type: "multiple_choice",
      });

      // Read quiz data only from response.metadata.quiz
      let quizData: QuizDetail | null = null;
      if (response.metadata?.quiz) {
        if (typeof response.metadata.quiz === "string") {
          try {
            quizData = JSON.parse(response.metadata.quiz);
          } catch {
            // ignore
          }
        } else {
          quizData = response.metadata.quiz as QuizDetail;
        }
      }

      if (quizData && quizData.questions && quizData.questions.length > 0) {
        setQuizDetail(quizData);
      } else {
        toast.error("The model failed to return a structured quiz schema. Please try again.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to generate quiz.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectAnswer = (questionId: string, optionIdx: number) => {
    if (isSubmitting || quizResult) return;
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionIdx,
    }));
  };

  const handleSubmitQuiz = async () => {
    if (!quizDetail || isSubmitting || quizResult) return;

    const unanswered = quizDetail.questions.filter((q) => selectedAnswers[q.id] === undefined);
    if (unanswered.length > 0) {
      toast.error("Please answer all questions before submitting.");
      return;
    }

    setIsSubmitting(true);
    try {
      const responses: QuizResponseItem[] = quizDetail.questions.map((q) => ({
        question_id: q.id,
        selected_option_id: selectedAnswers[q.id],
      }));

      const submissionPayload = {
        attempt_number: 1,
        idempotency_key: uuidv4(),
        responses,
      };

      const result = await quizService.submitQuiz(quizDetail.quiz_id, submissionPayload);
      setQuizResult(result);
    } catch (err: any) {
      toast.error(err.message || "Failed to grade quiz.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = () => {
    setQuizDetail(null);
    setQuizResult(null);
    setSelectedAnswers({});
  };

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4.5 custom-scrollbar">
      {/* 1. Configuration UI */}
      {!quizDetail && !isLoading && (
        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-col">
              <span className="text-sm font-bold text-zinc-200">Interactive Quiz Maker</span>
              <span className="text-xs text-zinc-500 font-medium">Test your comprehension on the document</span>
            </div>
            <Award className="h-5 w-5 text-primary/80" />
          </div>

          <div className="grid grid-cols-2 gap-2 mt-1">
            {/* Difficulty */}
            <div className="flex flex-col gap-1">
              <label htmlFor="quiz-difficulty" className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Difficulty</label>
              <select
                id="quiz-difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as any)}
                className="h-9 px-2 rounded-lg border border-zinc-800 bg-zinc-950 text-xs text-zinc-300 outline-none"
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>

            {/* Questions count */}
            <div className="flex flex-col gap-1">
              <label htmlFor="quiz-questions" className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Questions</label>
              <select
                id="quiz-questions"
                value={numQuestions}
                onChange={(e) => setNumQuestions(Number(e.target.value))}
                className="h-9 px-2 rounded-lg border border-zinc-800 bg-zinc-950 text-xs text-zinc-300 outline-none"
              >
                {[3, 5, 10, 15, 20].map((num) => (
                  <option key={num} value={num}>
                    {num} questions
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleGenerateQuiz}
            disabled={disabled || isLoading}
            className="flex items-center justify-center gap-2 h-10 w-full rounded-full bg-primary text-white text-sm font-semibold hover:bg-primary-dark transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:scale-100 disabled:cursor-not-allowed mt-2 cursor-pointer"
          >
            <Sparkles className="h-4.5 w-4.5" />
            Generate Quiz
          </button>
        </div>
      )}

      {/* 2. Loading State */}
      {isLoading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-2.5 text-zinc-500 min-h-[220px]">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="text-xs font-semibold tracking-wide">
            Synthesizing study questions...
          </span>
        </div>
      )}

      {/* 3. Render Quiz Questions */}
      {quizDetail && !quizResult && (
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h5 className="text-sm font-bold text-zinc-200 truncate">{quizDetail.title}</h5>
            <span className="text-[10px] bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full text-zinc-400 font-mono">
              Multiple Choice
            </span>
          </div>

          <div className="flex flex-col gap-4">
            {quizDetail.questions.map((q, idx) => (
              <div key={q.id} className="p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/10">
                <span className="text-xs font-bold text-zinc-500 block mb-2 uppercase tracking-wider">
                  Question {idx + 1}
                </span>
                <p className="text-sm font-semibold text-zinc-200 leading-relaxed mb-3">
                  {q.question_text}
                </p>

                {/* Option radios */}
                <div className="flex flex-col gap-2">
                  {q.options.map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === optIdx;
                    return (
                      <button
                        key={optIdx}
                        onClick={() => handleSelectAnswer(q.id, optIdx)}
                        disabled={isSubmitting}
                        className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg border text-left text-xs font-semibold transition-all duration-200 cursor-pointer ${
                          isSelected
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-zinc-800 hover:border-zinc-700 bg-zinc-950/40 text-zinc-400 hover:text-zinc-300"
                        }`}
                      >
                        <div className={`h-5 w-5 shrink-0 flex items-center justify-center rounded-full border text-[10px] font-bold font-mono ${
                          isSelected ? "border-primary bg-primary text-white" : "border-zinc-800 bg-zinc-900 text-zinc-500"
                        }`}>
                          {String.fromCharCode(65 + optIdx)}
                        </div>
                        <span className="flex-1 leading-snug">{opt}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Submit Action */}
          <button
            onClick={handleSubmitQuiz}
            disabled={isSubmitting}
            className="flex items-center justify-center gap-2 h-10 w-full rounded-full bg-primary text-white text-sm font-semibold hover:bg-primary-dark transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:scale-100 disabled:cursor-not-allowed mt-2 cursor-pointer"
          >
            {isSubmitting ? (
              <Loader2 className="h-4.5 w-4.5 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4.5 w-4.5" />
            )}
            Submit Quiz
          </button>
        </div>
      )}

      {/* 4. Render Quiz Graded Results */}
      {quizResult && (
        <QuizResult result={quizResult} onRetry={handleRetry} />
      )}
    </div>
  );
};
