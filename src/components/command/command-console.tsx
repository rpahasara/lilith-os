"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useCommand } from "./command-provider";
import { CommandReview } from "./command-review";
import { CommandProgress } from "./command-progress";
import { ApprovalRequest } from "./approval-request";
import { CommandResult } from "./command-result";
import { CommandUnsupported } from "./command-unsupported";

/**
 * The active-command console. Renders exactly one lifecycle surface for the
 * active task, driven purely by its status — review → progress → (approval) →
 * result / capability boundary. Progressive disclosure: nothing shows until
 * there is an active command.
 */
export function CommandConsole({ onEditRequest }: { onEditRequest?: (text: string) => void }) {
  const { activeTask, run, approve, deny, cancel, retry, resume, discard, dismissActive } =
    useCommand();

  if (!activeTask) return null;
  const t = activeTask;

  let surface: React.ReactNode = null;

  switch (t.status) {
    case "draft":
    case "reviewing":
      surface = (
        <CommandReview
          task={t}
          onRun={() => run(t.taskId)}
          onEdit={() => {
            onEditRequest?.(t.userInput);
            discard(t.taskId);
          }}
          onCancel={() => discard(t.taskId)}
        />
      );
      break;
    case "queued":
    case "planning":
    case "running":
      surface = <CommandProgress task={t} onCancel={() => cancel(t.taskId)} />;
      break;
    case "waiting_for_approval":
      surface = (
        <div className="flex w-full flex-col gap-2.5">
          <CommandProgress task={t} onCancel={() => cancel(t.taskId)} />
          <ApprovalRequest task={t} onApprove={() => approve(t.taskId)} onDeny={() => deny(t.taskId)} />
        </div>
      );
      break;
    case "blocked":
      surface = <CommandUnsupported task={t} onClose={dismissActive} />;
      break;
    case "partial":
    case "succeeded":
    case "failed":
    case "cancelled":
      surface = (
        <CommandResult
          task={t}
          onRetry={() => retry(t.taskId)}
          onResume={() => resume(t.taskId)}
          onClose={dismissActive}
        />
      );
      break;
  }

  return (
    <div className="w-full max-w-xl">
      <AnimatePresence mode="wait">
        <motion.div
          key={t.status}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {surface}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
